import os
import json
from pathlib import Path

import matplotlib.pyplot as plt
from dotenv import load_dotenv
from groq import Groq


# --------------------------------------------------
# Configuration
# --------------------------------------------------

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")

if not API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env file")

client = Groq(api_key=API_KEY)

MODEL = "llama-3.3-70b-versatile"

BASE_DIR = Path(__file__).parent

JOB_DESCRIPTION_PATH = BASE_DIR / "inputs" / "job_description.md"
PROFILES_DIR = BASE_DIR / "inputs" / "profiles"
OUTPUT_DIR = BASE_DIR / "outputs"


# --------------------------------------------------
# File Handling
# --------------------------------------------------

def read_job_description():
    """Read the job description from the input file."""

    if not JOB_DESCRIPTION_PATH.exists():
        raise FileNotFoundError(
            f"Job description not found: {JOB_DESCRIPTION_PATH}"
        )

    return JOB_DESCRIPTION_PATH.read_text(encoding="utf-8")


def read_candidate_profiles():
    """Read all candidate markdown/text files."""

    candidates = []

    for file_path in sorted(PROFILES_DIR.glob("*")):

        if file_path.suffix.lower() not in [".md", ".txt"]:
            continue

        content = file_path.read_text(encoding="utf-8")

        candidates.append({
            "name": file_path.stem,
            "content": content
        })

    if not candidates:
        raise FileNotFoundError(
            "No candidate profile files found."
        )

    return candidates


# --------------------------------------------------
# Groq Analysis
# --------------------------------------------------

def analyze_candidates(job_description, candidates):

    candidate_text = ""

    for candidate in candidates:

        candidate_text += f"""
----------------------------------------
Candidate: {candidate['name']}
----------------------------------------

{candidate['content']}

"""

    prompt = f"""
You are an AI HR Resume Screening Assistant.

Your task is to objectively evaluate multiple candidate profiles
against a given job description.

========================
JOB DESCRIPTION
========================

{job_description}

========================
CANDIDATE PROFILES
========================

{candidate_text}

========================
EVALUATION TASK
========================

First, understand the requirements of the job description.

Then evaluate EVERY candidate independently against those requirements.

For every candidate, evaluate the following six categories:

1. Technical Skills - 30 points
2. Experience - 20 points
3. Education - 10 points
4. Certifications - 10 points
5. Domain Knowledge - 15 points
6. Soft Skills - 15 points

Total = 100 points.

========================
SCORING GUIDELINES
========================

Technical Skills (30 points):
Evaluate how closely the candidate's technical skills match
the technologies and skills required by the job description.

Experience (20 points):
Evaluate relevant internships, professional experience,
projects, and practical experience related to the role.

Education (10 points):
Evaluate how well the candidate's educational background
matches the requirements of the job.

Certifications (10 points):
Evaluate relevant certifications mentioned in the profile.
Do not give points for certifications that are not listed.

Domain Knowledge (15 points):
Evaluate the candidate's understanding of the domain,
such as backend development, databases, APIs, cloud,
or other areas relevant to the job.

Soft Skills (15 points):
Evaluate communication, teamwork, problem solving,
adaptability, leadership, and other soft skills explicitly
mentioned in the candidate profile.

========================
IMPORTANT RULES
========================

1. Use ONLY information provided in the job description
   and candidate profiles.

2. Never invent skills, experience, certifications,
   education, or achievements.

3. If a skill or qualification is not mentioned,
   treat it as missing information rather than assuming
   that the candidate has it.

4. Give higher scores to candidates whose skills and
   experience directly match the job requirements.

5. Consider both required and preferred qualifications.

6. The individual category scores MUST add up exactly
   to the candidate's final score.

7. Rank ALL candidates from highest score to lowest score.

8. Recommend the Top 5 candidates.
   If fewer than 5 candidates exist, recommend all candidates.

9. Base hiring recommendations on the candidate's
   actual score and evidence from their profile.

10. Do not discriminate based on age, gender, race,
    religion, nationality, or any other protected
    characteristic.

========================
RECOMMENDATION GUIDELINES
========================

Use one of these recommendations:

90-100:
"Strong Hire"

80-89:
"Hire"

70-79:
"Consider for Hire"

60-69:
"Consider for Junior Role"

Below 60:
"Not Recommended"

========================
JOB SUMMARY
========================

Create a concise 2-4 sentence summary of the job description.
The summary should mention the main role, important technical
requirements, experience expectations, and key qualifications.

========================
OUTPUT FORMAT
========================

Return ONLY valid JSON.

Use exactly this structure:

{{
    "job_summary": "2-4 sentence summary of the job description",

    "candidates": [
        {{
            "name": "candidate1",

            "technical_skills": 0,
            "experience": 0,
            "education": 0,
            "certifications": 0,
            "domain_knowledge": 0,
            "soft_skills": 0,

            "score": 0,

            "remarks": "Clear explanation of why this score was given.",

            "strengths": [
                "strength 1",
                "strength 2"
            ],

            "weaknesses": [
                "weakness 1",
                "weakness 2"
            ],

            "recommendation": "Strong Hire"
        }}
    ],

    "top_5": [
        "candidate1",
        "candidate2"
    ],

    "hiring_recommendation":
        "Overall hiring recommendation based on the candidate rankings."
}}

Make sure every candidate is included exactly once.
"""
    try:
       response = client.chat.completions.create(
           model=MODEL,
           messages=[
               {
                   "role": "system",
                   "content": (
                        "You are an expert HR resume screening assistant. "
                        "Return only valid JSON."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
    except Exception as e:
        raise RuntimeError(
            f"Groq API request failed: {e}"
        )
    try:
        result = response.choices[0].message.content

        if not result:
            raise ValueError("Groq returned an empty response.")

        result = result.strip()

        if result.startswith("```"):
            result = result.replace("```json", "")
            result = result.replace("```", "")
            result = result.strip()

        return json.loads(result)

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        raise RuntimeError(
            f"Invalid AI response received from Groq: {e}"
        )


# --------------------------------------------------
# Ranking
# --------------------------------------------------

def rank_candidates(results):

    results["candidates"].sort(
        key=lambda candidate: candidate["score"],
        reverse=True
    )

    results["top_5"] = [
        candidate["name"]
        for candidate in results["candidates"][:5]
    ]

    return results


# --------------------------------------------------
# Markdown Report
# --------------------------------------------------

def generate_report(results):

    OUTPUT_DIR.mkdir(exist_ok=True)

    report_path = OUTPUT_DIR / "report.md"

    candidates = results["candidates"]

    # --------------------------------------------------
    # Report Header
    # --------------------------------------------------

    report = "# AI HR Resume Screening Report\n\n"

    report += (
        "> AI-powered candidate evaluation and ranking "
        "using Groq LLM.\n\n"
    )

    # --------------------------------------------------
    # Job Summary
    # --------------------------------------------------

    report += "## Job Summary\n\n"

    report += results["job_summary"]

    report += "\n\n"

    # --------------------------------------------------
    # Screening Overview
    # --------------------------------------------------

    report += "## Screening Overview\n\n"

    total_candidates = len(candidates)

    top_candidate = candidates[0]

    report += (
        f"- **Total Candidates:** {total_candidates}\n"
    )

    report += (
        f"- **Top Candidate:** {top_candidate['name']}\n"
    )

    report += (
        f"- **Highest Score:** "
        f"{top_candidate['score']}/100\n"
    )

    report += "\n"

    # --------------------------------------------------
    # Candidate Evaluation
    # --------------------------------------------------

    report += "## Candidate Evaluation\n\n"

    report += (
        "| Rank | Candidate | Score | Recommendation | Remarks |\n"
    )

    report += (
        "|---:|---|---:|---|---|\n"
    )

    for index, candidate in enumerate(
        candidates,
        start=1
    ):

        report += (
            f"| {index} | "
            f"{candidate['name']} | "
            f"{candidate['score']}/100 | "
            f"{candidate['recommendation']} | "
            f"{candidate['remarks']} |\n"
        )

    report += "\n"

    # --------------------------------------------------
    # Detailed Evaluation
    # --------------------------------------------------

    report += "## Detailed Candidate Evaluation\n\n"

    for index, candidate in enumerate(
        candidates,
        start=1
    ):

        report += (
            f"### {index}. {candidate['name']}\n\n"
        )

        report += (
            f"**Overall Score:** "
            f"{candidate['score']}/100\n\n"
        )

        report += (
            f"**Recommendation:** "
            f"{candidate['recommendation']}\n\n"
        )

        # Category scores
        report += "#### Category Scores\n\n"

        report += "| Category | Score | Maximum |\n"
        report += "|---|---:|---:|\n"

        report += (
            f"| Technical Skills | "
            f"{candidate['technical_skills']}/30 | 30 |\n"
        )

        report += (
            f"| Experience | "
            f"{candidate['experience']}/20 | 20 |\n"
        )

        report += (
            f"| Education | "
            f"{candidate['education']}/10 | 10 |\n"
        )

        report += (
            f"| Certifications | "
            f"{candidate['certifications']}/10 | 10 |\n"
        )

        report += (
            f"| Domain Knowledge | "
            f"{candidate['domain_knowledge']}/15 | 15 |\n"
        )

        report += (
            f"| Soft Skills | "
            f"{candidate['soft_skills']}/15 | 15 |\n"
        )

        report += "\n"

        # Remarks
        report += "#### Evaluation Remarks\n\n"

        report += candidate["remarks"]

        report += "\n\n"

        # Strengths
        report += "#### Strengths\n\n"

        for strength in candidate["strengths"]:
            report += f"- {strength}\n"

        report += "\n"

        # Weaknesses
        report += "#### Areas for Improvement\n\n"

        if candidate["weaknesses"]:

            for weakness in candidate["weaknesses"]:
                report += f"- {weakness}\n"

        else:

            report += "- None identified.\n"

        report += "\n"

    # --------------------------------------------------
    # Top 5 Candidates
    # --------------------------------------------------

    report += "## Top 5 Candidates\n\n"

    for index, candidate_name in enumerate(
        results["top_5"],
        start=1
    ):

        # Find candidate information
        candidate = next(
            candidate
            for candidate in candidates
            if candidate["name"] == candidate_name
        )

        report += (
            f"{index}. **{candidate_name}** — "
            f"{candidate['score']}/100 — "
            f"{candidate['recommendation']}\n"
        )

    report += "\n"

    # --------------------------------------------------
    # Hiring Recommendation
    # --------------------------------------------------

    report += "## Hiring Recommendation\n\n"

    report += results["hiring_recommendation"]

    report += "\n\n"

    # --------------------------------------------------
    # Footer
    # --------------------------------------------------

    report += "---\n\n"

    report += (
        "*Generated automatically by the "
        "AI HR Resume Screening Assistant.*\n"
    )

    # --------------------------------------------------
    # Save Report
    # --------------------------------------------------

    report_path.write_text(
        report,
        encoding="utf-8"
    )

    print(f"Report saved to: {report_path}")


# --------------------------------------------------
# Chart Generation
# --------------------------------------------------

def generate_chart(results):

    OUTPUT_DIR.mkdir(exist_ok=True)

    candidates = results["candidates"]

    names = [
        candidate["name"]
        for candidate in candidates
    ]

    scores = [
        candidate["score"]
        for candidate in candidates
    ]

    plt.figure(figsize=(10, 6))

    bars = plt.bar(names, scores)

    plt.xlabel("Candidates")
    plt.ylabel("Score out of 100")
    plt.title("AI HR Candidate Screening Scores")

    # Keep the score range consistent
    plt.ylim(0, 100)

    # Add score labels above bars
    for bar, score in zip(bars, scores):

        plt.text(
            bar.get_x() + bar.get_width() / 2,
            score + 1,
            f"{score}/100",
            ha="center",
            va="bottom",
            fontweight="bold"
        )

    # Improve candidate labels
    plt.xticks(
        range(len(names)),
        names,
        rotation=30,
        ha="right"
    )

    plt.grid(
        axis="y",
        linestyle="--",
        alpha=0.3
    )

    plt.tight_layout()

    chart_path = OUTPUT_DIR / "scores.png"

    plt.savefig(
        chart_path,
        dpi=150,
        bbox_inches="tight"
    )

    plt.close()

    print(f"Chart saved to: {chart_path}")


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    print("\n======================================")
    print(" AI HR Resume Screening Assistant")
    print("======================================\n")

    print("Reading job description...")

    job_description = read_job_description()

    print("Reading candidate profiles...")

    candidates = read_candidate_profiles()

    print(f"Found {len(candidates)} candidates.")

    print("\nSending candidates to Groq AI...")

    results = analyze_candidates(
        job_description,
        candidates
    )

    print("AI analysis completed.")

    print("\nRanking candidates...")

    results = rank_candidates(results)

    print("\nCandidate Ranking")
    print("=================")

    for index, candidate in enumerate(
        results["candidates"],
        start=1
    ):

        print(
            f"{index}. "
            f"{candidate['name']} - "
            f"{candidate['score']}/100"
        )

    print("\nGenerating report...")

    generate_report(results)

    print("\nGenerating chart...")

    generate_chart(results)

    print("\n======================================")
    print(" Project completed successfully!")
    print("======================================\n")


if __name__ == "__main__":

    try:
        main()

    except FileNotFoundError as e:
        print(f"\n❌ File Error: {e}")

    except RuntimeError as e:
        print(f"\n❌ Application Error: {e}")

    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")