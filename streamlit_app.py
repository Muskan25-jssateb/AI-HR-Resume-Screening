import os
import json

import streamlit as st
import matplotlib.pyplot as plt
from pypdf import PdfReader
from docx import Document
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")

if not API_KEY:
    st.error(
        "GROQ_API_KEY is missing. "
        "Please configure your .env file."
    )
    st.stop()

client = Groq(api_key=API_KEY)

MODEL = "llama-3.1-8b-instant"


st.set_page_config(
    page_title="AI Resume Eligibility Checker",
    page_icon="📄",
    layout="wide"
)


def extract_pdf_text(uploaded_file):

    reader = PdfReader(uploaded_file)

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text


def extract_docx_text(uploaded_file):

    document = Document(uploaded_file)

    text = ""

    for paragraph in document.paragraphs:

        if paragraph.text.strip():
            text += paragraph.text + "\n"

    return text


def extract_txt_text(uploaded_file):

    return uploaded_file.read().decode(
        "utf-8",
        errors="ignore"
    )


def extract_resume_text(uploaded_file):

    file_type = uploaded_file.name.lower()

    if file_type.endswith(".pdf"):

        return extract_pdf_text(uploaded_file)

    elif file_type.endswith(".docx"):

        return extract_docx_text(uploaded_file)

    elif file_type.endswith(".txt"):

        return extract_txt_text(uploaded_file)

    else:

        raise ValueError(
            "Unsupported file format."
        )

def analyze_resume(resume_text, job_description):

    prompt = f"""
You are an AI Resume Eligibility Assistant.

Your task is to evaluate a candidate's resume against
a specific job description.

========================
JOB DESCRIPTION
========================

{job_description}

========================
CANDIDATE RESUME
========================

{resume_text}

========================
EVALUATION CRITERIA
========================

Evaluate the candidate using:

1. Technical Skills - 0 to 30 points
2. Experience - 0 to 20 points
3. Education - 0 to 10 points
4. Certifications - 0 to 10 points
5. Domain Knowledge - 0 to 15 points
6. Soft Skills - 0 to 15 points

Total maximum = 100 points.

STRICT SCORING LIMITS:

- Technical Skills MUST be between 0 and 30.
- Experience MUST be between 0 and 20.
- Education MUST be between 0 and 10.
- Certifications MUST be between 0 and 10.
- Domain Knowledge MUST be between 0 and 15.
- Soft Skills MUST be between 0 and 15.

NEVER give a category a score greater than its maximum.
NEVER give a negative score.

========================
IMPORTANT RULES
========================

1. Use ONLY information present in the resume
   and job description.

2. Never invent skills, experience, education,
   certifications, or achievements.

3. If something is not mentioned in the resume,
   treat it as missing information.

4. Do not assume that missing information means
   the candidate does not possess the skill.

5. Compare the candidate's actual qualifications
   against the job requirements.

6. The final score MUST be the sum of the
   six category scores.

7. Before returning the JSON, verify that every
   category score is within its allowed range.

8. Do not give bonus points beyond the maximum
   allowed for any category.

9. Do not consider protected characteristics such
   as gender, race, religion, nationality, age,
   disability, or other unrelated personal attributes.

========================
ELIGIBILITY LEVELS
========================

90-100:
"Strong Match"

80-89:
"Good Match"

70-79:
"Potential Match"

Below 70:
"Low Match"

========================
OUTPUT
========================

Return ONLY valid JSON.

Use exactly this structure:

{{
    "eligibility_status": "Strong Match",

    "score": 0,

    "category_scores": {{
        "technical_skills": 0,
        "experience": 0,
        "education": 0,
        "certifications": 0,
        "domain_knowledge": 0,
        "soft_skills": 0
    }},

    "matched_skills": [
        "skill 1",
        "skill 2"
    ],

    "missing_skills": [
        "skill 1",
        "skill 2"
    ],

    "strengths": [
        "strength 1",
        "strength 2"
    ],

    "improvement_suggestions": [
        "suggestion 1",
        "suggestion 2"
    ],

    "summary": "A concise explanation of the candidate's overall match."
}}
"""

    try:

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an objective AI resume "
                        "eligibility assistant. "
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
            raise ValueError(
                "Groq returned an empty response."
            )

        return json.loads(result)

    except (json.JSONDecodeError, ValueError) as e:

        raise RuntimeError(
            f"Invalid AI response: {e}"
        )

def validate_analysis(analysis):

    required_categories = {
        "technical_skills": 30,
        "experience": 20,
        "education": 10,
        "certifications": 10,
        "domain_knowledge": 15,
        "soft_skills": 15
    }

    category_scores = analysis.get(
        "category_scores",
        {}
    )

    # Check that every category exists
    for category, maximum in required_categories.items():

        if category not in category_scores:

            raise ValueError(
                f"Missing category score: {category}"
            )

        score = category_scores[category]

        # Check score is numeric
        if not isinstance(score, (int, float)):

            raise ValueError(
                f"Invalid score for {category}"
            )

        # Check score is within allowed range
        if score < 0 or score > maximum:

            raise ValueError(
                f"Invalid score for {category}: "
                f"{score}/{maximum}"
            )

    # Calculate the score ourselves
    calculated_score = sum(
        category_scores.values()
    )

    # Make Python's calculated score the source of truth
    analysis["score"] = calculated_score

    # Determine eligibility level ourselves
    if calculated_score >= 90:

        analysis["eligibility_status"] = "Strong Match"

    elif calculated_score >= 80:

        analysis["eligibility_status"] = "Good Match"

    elif calculated_score >= 70:

        analysis["eligibility_status"] = "Potential Match"

    else:

        analysis["eligibility_status"] = "Low Match"

    return True

def get_eligibility_message(score, missing_skills):

    if score >= 90:

        message = (
            "You are a very strong match for this position. "
            "Your profile aligns closely with the requirements "
            "of the selected job."
        )

    elif score >= 80:

        message = (
            "You are a strong candidate for this position. "
            "Your profile matches most of the important "
            "requirements, with a few areas that could be improved."
        )

    elif score >= 70:

        message = (
            "You meet several requirements for this position, "
            "but there are some areas you should strengthen "
            "before applying."
        )

    else:

        message = (
            "Your current profile does not closely match this "
            "position. Consider strengthening the missing skills "
            "before applying."
        )

    if missing_skills:

        if len(missing_skills) == 1:

            message += (
                f" Your main skill gap is "
                f"{missing_skills[0]}."
            )

        else:

            important_gaps = ", ".join(
                missing_skills[:3]
            )

            message += (
                f" Some important skill gaps include "
                f"{important_gaps}."
            )

    return message


def generate_candidate_report(
    analysis,
    candidate_name,
    job_name
):

    category_scores = analysis["category_scores"]

    report = "# AI Resume Eligibility Report\n\n"

    report += f"## Candidate\n\n"
    report += f"**Resume:** {candidate_name}\n\n"

    report += f"**Position:** {job_name}\n\n"

    report += "---\n\n"

    # ----------------------------------------------
    # Eligibility
    # ----------------------------------------------

    report += "## Eligibility Result\n\n"

    report += (
        f"**Score:** {analysis['score']}/100\n\n"
    )

    report += (
        f"**Match Level:** "
        f"{analysis['eligibility_status']}\n\n"
    )

    # ----------------------------------------------
    # Summary
    # ----------------------------------------------

    report += "## AI Summary\n\n"

    report += analysis["summary"]

    report += "\n\n"

    # ----------------------------------------------
    # Category Scores
    # ----------------------------------------------

    report += "## Category Scores\n\n"

    report += "| Category | Score | Maximum |\n"
    report += "|---|---:|---:|\n"

    report += (
        f"| Technical Skills | "
        f"{category_scores['technical_skills']}/30 | 30 |\n"
    )

    report += (
        f"| Experience | "
        f"{category_scores['experience']}/20 | 20 |\n"
    )

    report += (
        f"| Education | "
        f"{category_scores['education']}/10 | 10 |\n"
    )

    report += (
        f"| Certifications | "
        f"{category_scores['certifications']}/10 | 10 |\n"
    )

    report += (
        f"| Domain Knowledge | "
        f"{category_scores['domain_knowledge']}/15 | 15 |\n"
    )

    report += (
        f"| Soft Skills | "
        f"{category_scores['soft_skills']}/15 | 15 |\n"
    )

    report += "\n"

    # ----------------------------------------------
    # Matched Skills
    # ----------------------------------------------

    report += "## Matched Skills\n\n"

    for skill in analysis["matched_skills"]:

        report += f"- ✓ {skill}\n"

    report += "\n"

    # ----------------------------------------------
    # Skill Gaps
    # ----------------------------------------------

    report += "## Skill Gaps\n\n"

    if analysis["missing_skills"]:

        for skill in analysis["missing_skills"]:

            report += f"- ⚠ {skill}\n"

    else:

        report += (
            "No significant skill gaps identified.\n"
        )

    report += "\n"

    # ----------------------------------------------
    # Strengths
    # ----------------------------------------------

    report += "## Strengths\n\n"

    for strength in analysis["strengths"]:

        report += f"- {strength}\n"

    report += "\n"

    # ----------------------------------------------
    # Improvements
    # ----------------------------------------------

    report += "## How to Improve\n\n"

    for suggestion in analysis[
        "improvement_suggestions"
    ]:

        report += f"- {suggestion}\n"

    report += "\n"

    report += "---\n\n"

    report += (
        "*Generated by AI Resume Eligibility Checker.*\n"
    )

    return report

def generate_hr_report(
    results,
    job_name
):

    report = "# AI HR Resume Screening Report\n\n"

    report += f"## Job Position\n\n"
    report += f"**{job_name}**\n\n"

    report += "---\n\n"

    # --------------------------------------------------
    # Candidate Ranking
    # --------------------------------------------------

    report += "## Candidate Ranking\n\n"

    report += (
        "| Rank | Candidate | Score | Match |\n"
    )

    report += (
        "|---:|---|---:|---|\n"
    )

    for rank, result in enumerate(
        results,
        start=1
    ):

        analysis = result["analysis"]

        report += (
            f"| {rank} | "
            f"{result['candidate']} | "
            f"{analysis['score']}/100 | "
            f"{analysis['eligibility_status']} |\n"
        )

    report += "\n"

    # --------------------------------------------------
    # Top 5
    # --------------------------------------------------

    report += "## Top 5 Candidates\n\n"

    for rank, result in enumerate(
        results[:5],
        start=1
    ):

        candidate = result["candidate"]

        analysis = result["analysis"]

        report += (
            f"### {rank}. {candidate}\n\n"
        )

        report += (
            f"**Score:** "
            f"{analysis['score']}/100\n\n"
        )

        report += (
            f"**Match:** "
            f"{analysis['eligibility_status']}\n\n"
        )

        report += (
            f"**Summary:** "
            f"{analysis['summary']}\n\n"
        )

        # Category scores

        report += "#### Category Scores\n\n"

        category_scores = analysis[
            "category_scores"
        ]

        report += (
            f"- Technical Skills: "
            f"{category_scores['technical_skills']}/30\n"
        )

        report += (
            f"- Experience: "
            f"{category_scores['experience']}/20\n"
        )

        report += (
            f"- Education: "
            f"{category_scores['education']}/10\n"
        )

        report += (
            f"- Certifications: "
            f"{category_scores['certifications']}/10\n"
        )

        report += (
            f"- Domain Knowledge: "
            f"{category_scores['domain_knowledge']}/15\n"
        )

        report += (
            f"- Soft Skills: "
            f"{category_scores['soft_skills']}/15\n\n"
        )

        # Matched skills

        report += "#### Matched Skills\n\n"

        for skill in analysis[
            "matched_skills"
        ]:

            report += f"- {skill}\n"

        report += "\n"

        # Missing skills

        report += "#### Skill Gaps\n\n"

        if analysis["missing_skills"]:

            for skill in analysis[
                "missing_skills"
            ]:

                report += f"- {skill}\n"

        else:

            report += (
                "No significant skill gaps identified.\n"
            )

        report += "\n"

        # Strengths

        report += "#### Strengths\n\n"

        for strength in analysis[
            "strengths"
        ]:

            report += f"- {strength}\n"

        report += "\n"

        # Improvements

        report += "#### Improvement Areas\n\n"

        for suggestion in analysis[
            "improvement_suggestions"
        ]:

            report += f"- {suggestion}\n"

        report += "\n---\n\n"

    # --------------------------------------------------
    # Hiring Recommendation
    # --------------------------------------------------

    if results:

        best_candidate = results[0]

        best_analysis = best_candidate[
            "analysis"
        ]

        report += "## Hiring Recommendation\n\n"

        report += (
            f"**Top-ranked candidate:** "
            f"{best_candidate['candidate']}\n\n"
        )

        report += (
            f"**Score:** "
            f"{best_analysis['score']}/100\n\n"
        )

        report += (
            "The ranking is based on the AI-assisted "
            "comparison of candidate profiles against "
            "the selected job description. Human review "
            "is recommended before making final hiring "
            "decisions.\n"
        )

    return report

def create_score_chart(category_scores):

    categories = [
        "Technical Skills",
        "Experience",
        "Education",
        "Certifications",
        "Domain Knowledge",
        "Soft Skills"
    ]

    scores = [
        category_scores["technical_skills"],
        category_scores["experience"],
        category_scores["education"],
        category_scores["certifications"],
        category_scores["domain_knowledge"],
        category_scores["soft_skills"]
    ]

    maximum_scores = [
        30,
        20,
        10,
        10,
        15,
        15
    ]

    fig, ax = plt.subplots(
        figsize=(9, 5)
    )

    y_positions = range(len(categories))

    ax.barh(
        y_positions,
        maximum_scores,
        alpha=0.25,
        label="Maximum"
    )

    ax.barh(
        y_positions,
        scores,
        alpha=0.9,
        label="Candidate Score"
    )

    ax.set_yticks(y_positions)
    ax.set_yticklabels(categories)

    ax.set_xlabel("Score")

    ax.set_title(
        "Resume Eligibility — Category Scores"
    )

    ax.legend()

    ax.invert_yaxis()

    plt.tight_layout()

    return fig
def create_candidate_comparison_chart(results):

    candidates = [
        result["candidate"]
        for result in results
    ]

    scores = [
        result["analysis"]["score"]
        for result in results
    ]

    fig, ax = plt.subplots(
        figsize=(10, 5)
    )

    ax.bar(
        candidates,
        scores
    )

    ax.set_xlabel("Candidates")
    ax.set_ylabel("Score")
    ax.set_title(
        "Candidate Score Comparison"
    )

    ax.set_ylim(0, 100)

    plt.xticks(
        rotation=45,
        ha="right"
    )

    plt.tight_layout()

    return fig

# --------------------------------------------------
# UI
# --------------------------------------------------

# --------------------------------------------------
# Application Mode
# --------------------------------------------------

st.sidebar.title("AI Resume Match")

mode = st.sidebar.radio(
    "Choose your mode",
    [
        "👤 Candidate",
        "🏢 HR"
    ]
)

# --------------------------------------------------
# Candidate Mode
# --------------------------------------------------

def candidate_mode():
    # --------------------------------------------------
    # Landing Header
    # --------------------------------------------------

    st.markdown(
    """
    <div style="
        padding: 2.5rem 1rem;
        text-align: center;
        border-radius: 15px;
        margin-bottom: 2rem;
    ">

    <h1 style="font-size: 3rem;">
    🤖 AI Resume Match
    </h1>

    <p style="
    font-size: 1.25rem;
    margin-top: 0.5rem;
    ">
    Know how well your resume matches your dream job.
    </p>

    <p style="
    font-size: 1rem;
    opacity: 0.8;
    ">
    AI-powered resume analysis • Skill gap detection •
    Personalized recommendations
    </p>

    </div>
    """,
    unsafe_allow_html=True
    )


    # --------------------------------------------------
    # Start New Analysis
    # --------------------------------------------------

    if "analysis" in st.session_state:

        if st.button(
            "🔄 Start New Analysis",
            use_container_width=True
        ):

            del st.session_state["analysis"]

            st.session_state.pop(
                "uploaded_filename",
                None
            )

            st.rerun()


    # --------------------------------------------------
    # How It Works
    # --------------------------------------------------

    st.markdown(
        """
        ### How it works

        **📄 Upload Resume** → **💼 Select Job** →
        **🤖 AI Analysis** → **📊 Get Your Match Score**
        """
    )

    st.divider()


    # --------------------------------------------------
    # Resume Upload
    # --------------------------------------------------

    st.header("📄 Step 1: Upload Your Resume")

    uploaded_file = st.file_uploader(
        "Upload your resume",
        type=["pdf", "docx", "txt"],
        help="Supported formats: PDF, DOCX and TXT"
    )

    if uploaded_file:

        if (
            "uploaded_filename"
            not in st.session_state
            or st.session_state["uploaded_filename"]
            != uploaded_file.name
        ):

            st.session_state.pop(
                "analysis",
                None
            )

            st.session_state[
                "uploaded_filename"
            ] = uploaded_file.name

    resume_text = ""


    if uploaded_file:

        try:

            resume_text = extract_resume_text(
                uploaded_file
            )

            if resume_text.strip():

                st.success(
                    f"✓ Resume uploaded successfully: "
                    f"{uploaded_file.name}"
                )

            else:

                st.warning(
                    "The resume was uploaded, but no readable "
                    "text could be extracted."
                )

        except Exception as e:

            st.error(
                f"Could not read the resume: {e}"
            )


    # --------------------------------------------------
    # Job Description
    # --------------------------------------------------

    # --------------------------------------------------
    # Job Selection
    # --------------------------------------------------

    st.header("💼 Step 2: Select a Job")

    JOBS_DIR = "jobs"


    def load_jobs():

        jobs = {}

        if not os.path.exists(JOBS_DIR):
            return jobs

        for file in os.listdir(JOBS_DIR):

            if file.endswith(".md"):

                file_path = os.path.join(
                    JOBS_DIR,
                    file
                )

                with open(
                    file_path,
                    "r",
                    encoding="utf-8"
                ) as f:

                    job_description = f.read()

                job_name = file.replace(
                    ".md",
                    ""
                ).replace(
                    "_",
                    " "
                ).title()

                jobs[job_name] = job_description

        return jobs


    jobs = load_jobs()


    if not jobs:

        st.error(
            "No job descriptions found. "
            "Please add job files inside the jobs folder."
        )

        st.stop()


    selected_job = st.selectbox(
        "Choose the position you want to apply for",
        list(jobs.keys())
    )


    job_description = jobs[selected_job]


    with st.expander(
        "View Job Description"
    ):

        st.markdown(
            job_description
        )


    # --------------------------------------------------
    # Analyze
    # --------------------------------------------------

    st.header("🤖 Step 3: Analyze Your Resume")

    analyze_button = st.button(
        "🚀 Analyze My Resume",
        type="primary",
        use_container_width=True
    )


    if analyze_button:

        if not uploaded_file:

            st.error(
                "Please upload your resume first."
            )

        elif not resume_text.strip():

            st.error(
                "No readable text was found in the resume."
            )

        elif not job_description.strip():

            st.error(
                "Please enter a job description."
            )

        else:

            with st.spinner(
                "Analyzing your resume with AI..."
            ):

                try:

                    analysis = analyze_resume(
                        resume_text,
                        job_description
                    )
                    validate_analysis(analysis)

                    st.session_state["analysis"] = analysis

                except (RuntimeError, ValueError) as e:

                    st.error(str(e))


    # --------------------------------------------------
    # Results
    # --------------------------------------------------

    if "analysis" in st.session_state:

        analysis = st.session_state["analysis"]

        score = analysis["score"]
        status = analysis["eligibility_status"]

        st.divider()

        st.header("📊 Resume Analysis")


        # --------------------------------------------------
        # Eligibility Result
        # --------------------------------------------------

        st.subheader("Eligibility Result")

        result_col1, result_col2, result_col3 = st.columns(
            [1, 2, 1]
        )

        with result_col1:

            st.metric(
                "Overall Score",
                f"{score}/100"
            )

        with result_col2:

            if score >= 90:

                st.success(
                    f"🟢 {status}"
                )

            elif score >= 80:

                st.success(
                    f"🟢 {status}"
                )

            elif score >= 70:

                st.warning(
                    f"🟡 {status}"
                )

            else:

                st.error(
                    f"🔴 {status}"
                )

        with result_col3:

            st.metric(
                "Resume",
                uploaded_file.name
                if uploaded_file
                else "Uploaded"
            )


        # --------------------------------------------------
        # Score Progress
        # --------------------------------------------------

        st.progress(
            min(max(score, 0), 100) / 100
        )

        # --------------------------------------------------
        # Candidate Recommendation
        # --------------------------------------------------

        recommendation = get_eligibility_message(
            score,
            analysis["missing_skills"]
        )

        st.subheader("🎯 What This Means")

        if score >= 90:

            st.success(recommendation)

        elif score >= 80:

            st.success(recommendation)

        elif score >= 70:

            st.warning(recommendation)

        else:

            st.error(recommendation)


        # --------------------------------------------------
        # AI Summary
        # --------------------------------------------------

        st.subheader("🧠 AI Summary")

        st.info(
            analysis["summary"]
        )


        # --------------------------------------------------
        # Category Scores
        # --------------------------------------------------

        st.subheader("📈 Category Scores")

        category_scores = analysis["category_scores"]

        categories = [
            ("Technical Skills", "technical_skills", 30),
            ("Experience", "experience", 20),
            ("Education", "education", 10),
            ("Certifications", "certifications", 10),
            ("Domain Knowledge", "domain_knowledge", 15),
            ("Soft Skills", "soft_skills", 15)
        ]

        for label, key, maximum in categories:

            current_score = category_scores[key]

            percentage = current_score / maximum

            score_col1, score_col2 = st.columns(
                [3, 1]
            )

            with score_col1:

                st.write(
                    f"**{label}**"
                )

                st.progress(
                    min(max(percentage, 0), 1)
                )

            with score_col2:

                st.write(
                    f"**{current_score}/{maximum}**"
                )

        # --------------------------------------------------
        # Score Chart
        # --------------------------------------------------

        st.subheader("📊 Score Breakdown")

        score_chart = create_score_chart(
            category_scores
        )

        st.pyplot(
            score_chart,
            use_container_width=True
        )

        plt.close(score_chart)


        # --------------------------------------------------
        # Skills
        # --------------------------------------------------

        st.subheader("🛠️ Skills Analysis")

        skill_col1, skill_col2 = st.columns(2)


        # Matched Skills

        with skill_col1:

            st.markdown(
                "### ✅ Matched Skills"
            )

            if analysis["matched_skills"]:

                for skill in analysis["matched_skills"]:

                    st.success(
                        f"✓ {skill}"
                    )

            else:

                st.write(
                    "No matching skills identified."
                )


        # Missing Skills

        with skill_col2:

            st.markdown(
                "### ⚠️ Skill Gaps"
            )

            if analysis["missing_skills"]:

                for skill in analysis["missing_skills"]:

                    st.warning(
                        f"⚠ {skill}"
                    )

            else:

                st.success(
                    "No significant skill gaps identified."
                )


        # --------------------------------------------------
        # Strengths and Improvements
        # --------------------------------------------------

        st.subheader("💡 Candidate Insights")

        insight_col1, insight_col2 = st.columns(2)


        with insight_col1:

            st.markdown(
                "### 💪 Strengths"
            )

            for strength in analysis["strengths"]:

                st.write(
                    f"• {strength}"
                )


        with insight_col2:

            st.markdown(
                "### 🚀 How to Improve"
            )

            for suggestion in analysis[
                "improvement_suggestions"
            ]:

                st.write(
                    f"• {suggestion}"
                )

        # --------------------------------------------------
        # Download Report
        # --------------------------------------------------

        st.divider()

        st.subheader("📄 Download Your Analysis")

        candidate_name = uploaded_file.name

        report = generate_candidate_report(
            analysis,
            candidate_name,
            selected_job
        )

        st.download_button(
            label="⬇️ Download My Analysis Report",
            data=report,
            file_name="resume_analysis.md",
            mime="text/markdown",
            use_container_width=True
        )

# --------------------------------------------------
# HR Mode
# --------------------------------------------------

def hr_mode():

    st.title("🏢 HR Screening Dashboard")

    st.write(
        "Upload multiple candidate resumes and compare "
        "their profiles against a selected job."
    )

    st.divider()

    # --------------------------------------------------
    # Job Selection
    # --------------------------------------------------

    st.header("💼 Step 1: Select a Job")

    JOBS_DIR = "jobs"

    jobs = {}

    if os.path.exists(JOBS_DIR):

        for file in os.listdir(JOBS_DIR):

            if file.endswith(".md"):

                file_path = os.path.join(
                    JOBS_DIR,
                    file
                )

                with open(
                    file_path,
                    "r",
                    encoding="utf-8"
                ) as f:

                    job_description = f.read()

                job_name = (
                    file
                    .replace(".md", "")
                    .replace("_", " ")
                    .title()
                )

                jobs[job_name] = job_description

    if not jobs:

        st.error(
            "No job descriptions found in the jobs folder."
        )

        return

    selected_job = st.selectbox(
        "Choose the position",
        list(jobs.keys())
    )

    job_description = jobs[selected_job]

    with st.expander("View Job Description"):

        st.markdown(
            job_description
        )

    # --------------------------------------------------
    # Resume Upload
    # --------------------------------------------------

    st.header("📄 Step 2: Upload Candidate Resumes")

    uploaded_files = st.file_uploader(
        "Upload candidate resumes",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="You can upload multiple candidate resumes."
    )

    if uploaded_files:

        st.success(
            f"{len(uploaded_files)} candidate(s) uploaded."
        )

        for file in uploaded_files:

            st.write(
                f"📄 {file.name}"
            )

            st.divider()

        analyze_candidates = st.button(
            "🚀 Analyze All Candidates",
            use_container_width=True
        )

        if analyze_candidates:

            if len(uploaded_files) < 2:

                st.warning(
                    "Please upload at least 2 candidate resumes."
                )

            else:

                st.session_state["hr_results"] = []

                progress = st.progress(0)

                status = st.empty()

                total_candidates = len(
                    uploaded_files
                )

                for index, uploaded_file in enumerate(
                    uploaded_files
                ):

                    status.write(
                        f"Analyzing "
                        f"{uploaded_file.name}..."
                    )

                    try:

                        # Extract resume text
                        resume_text = extract_resume_text(
                            uploaded_file
                        )

                        # Analyze candidate
                        analysis = analyze_resume(
                            resume_text,
                            job_description
                        )

                        # Validate AI response
                        validate_analysis(
                            analysis
                        )

                        # Store result
                        st.session_state[
                            "hr_results"
                        ].append(
                            {
                                "candidate":
                                    uploaded_file.name,

                                "analysis":
                                    analysis
                            }
                        )

                    except Exception as e:
                        error_message = str(e)
                        if "429" in error_message or "rate_limit" in error_message:

                            st.error(
                                "⚠️ Groq API rate limit reached. "
                                "Resume analysis has been paused. "
                                "Please try again after the limit resets."
                            )
                            break
                        else:
                            st.error(
                                f"Could not analyze "
                                f"{uploaded_file.name}: "
                                f"{error_message}"
                            )

                    progress.progress(
                        (index + 1) /
                        total_candidates
                    )

                status.success(
                    "Candidate analysis completed."
                )

                # --------------------------------------------------
                # Candidate Ranking
                # --------------------------------------------------

                results = st.session_state.get(
                    "hr_results",
                    []
                )

                if results:
                    # --------------------------------------------------
                    # Candidate Filters
                    # --------------------------------------------------

                    st.divider()

                    st.subheader(
                        "🔎 Filter Candidates"
                    )

                    filter_col1, filter_col2 = st.columns(2)

                    with filter_col1:

                        minimum_score = st.slider(
                            "Minimum Score",
                            min_value=0,
                            max_value=100,
                            value=0,
                            step=5
                        )

                    with filter_col2:

                        match_filter = st.selectbox(
                            "Match Status",
                            [
                                "All",
                                "Strong Match",
                                "Good Match",
                                "Potential Match",
                                "Low Match"
                            ]
                        )
                    filtered_results = []

                    for result in results:

                        analysis = result[
                            "analysis"
                        ]

                        score = analysis[
                            "score"
                        ]

                        status = analysis[
                            "eligibility_status"
                        ]

                        if score < minimum_score:
                            continue

                        if (
                            match_filter != "All"
                            and status != match_filter
                        ):
                            continue

                        filtered_results.append(
                            result
                        )
                    # Sort filtered candidates by score
                    filtered_results.sort(
                        key=lambda x: x["analysis"]["score"],
                        reverse=True
                    )   
                    # --------------------------------------------------
                    # Screening Statistics
                    # --------------------------------------------------

                    scores = [
                        result["analysis"]["score"]
                        for result in results
                    ]

                    total_candidates = len(
                        results
                    )

                    average_score = (
                        sum(scores) / total_candidates
                    )

                    highest_score = max(
                        scores
                    )

                    best_candidate = max(
                        results,
                        key=lambda x: x["analysis"]["score"]
                    )

                    best_candidate_name = (
                        best_candidate["candidate"]
                    )

                    col1, col2, col3 = st.columns(3)

                    with col1:

                        st.metric(
                            "👥 Candidates Screened",
                            total_candidates
                        )

                    with col2:

                        st.metric(
                            "📊 Average Score",
                            f"{average_score:.1f}/100"
                        )

                    with col3:

                        st.metric(
                            "🏆 Highest Score",
                            f"{highest_score}/100"
                        )

                    st.info(
                        f"🏆 **Top Candidate:** "
                        f"{best_candidate_name} — "
                        f"{highest_score}/100"
                    )

                    st.divider()

                    st.header(
                        "🏆 Candidate Ranking"
                    )

                    # Sort candidates by score
                    results.sort(
                        key=lambda x: x["analysis"]["score"],
                        reverse=True
                    )

                    # Display ranking
                    for rank, result in enumerate(
                        filtered_results,
                        start=1
                    ):

                        candidate = result[
                            "candidate"
                        ]

                        analysis = result[
                            "analysis"
                        ]

                        score = analysis[
                            "score"
                        ]

                        status = analysis[
                            "eligibility_status"
                        ]

                        st.write(
                            f"**{rank}. "
                            f"{candidate}**"
                        )

                        col1, col2 = st.columns(
                            [3, 1]
                        )

                        with col1:

                            st.progress(
                                score / 100
                            )

                        with col2:

                            st.write(
                                f"**{score}/100**"
                            )

                        st.caption(
                            status
                        )
                    st.divider()

                    st.subheader(
                        "📋 Screening Summary"
                    )

                    table_data = []

                    for rank, result in enumerate(
                        filtered_results,
                        start=1
                    ):

                        analysis = result[
                            "analysis"
                        ]

                        table_data.append(
                            {
                                "Rank": rank,
                                "Candidate":
                                    result["candidate"],
                                "Score":
                                    analysis["score"],
                                "Match":
                                    analysis[
                                        "eligibility_status"
                                    ]
                            }
                        )

                    st.dataframe(
                        table_data,
                        use_container_width=True,
                        hide_index=True
                    )
                    # --------------------------------------------------
                    # Candidate Comparison Chart
                    # --------------------------------------------------

                    st.divider()

                    st.subheader(
                        "📊 Candidate Score Comparison"
                    )

                    comparison_chart = create_candidate_comparison_chart(
                        filtered_results
                    )

                    st.pyplot(
                        comparison_chart,
                        use_container_width=True
                    )

                    plt.close(comparison_chart)
                                        # --------------------------------------------------
                    # Candidate Comparison
                    # --------------------------------------------------

                    if len(filtered_results) >= 2:

                        st.divider()

                        st.header(
                            "🔍 Compare Candidates"
                        )

                        candidate_names = [
                            result["candidate"]
                            for result in filtered_results
                        ]

                        # ----------------------------------------------
                        # Candidate Selection
                        # ----------------------------------------------

                        col1, col2 = st.columns(2)

                        with col1:

                            candidate_1_name = st.selectbox(
                                "Select Candidate 1",
                                candidate_names,
                                key="candidate_compare_1"
                            )

                        candidate_2_options = [
                            name
                            for name in candidate_names
                            if name != candidate_1_name
                        ]

                        with col2:

                            candidate_2_name = st.selectbox(
                                "Select Candidate 2",
                                candidate_2_options,
                                key="candidate_compare_2"
                            )

                        # ----------------------------------------------
                        # Get Candidate Data
                        # ----------------------------------------------

                        candidate_1 = next(
                            result
                            for result in filtered_results
                            if result["candidate"] == candidate_1_name
                        )

                        candidate_2 = next(
                            result
                            for result in filtered_results
                            if result["candidate"] == candidate_2_name
                        )

                        analysis_1 = candidate_1[
                            "analysis"
                        ]

                        analysis_2 = candidate_2[
                            "analysis"
                        ]

                        # ----------------------------------------------
                        # Overall Comparison
                        # ----------------------------------------------

                        st.subheader(
                            "📊 Overall Comparison"
                        )

                        comparison_data = {
                            "Metric": [
                                "Overall Score",
                                "Technical Skills",
                                "Experience",
                                "Education",
                                "Certifications",
                                "Domain Knowledge",
                                "Soft Skills"
                            ],

                            candidate_1_name: [
                                f"{analysis_1['score']}/100",
                                f"{analysis_1['category_scores']['technical_skills']}/30",
                                f"{analysis_1['category_scores']['experience']}/20",
                                f"{analysis_1['category_scores']['education']}/10",
                                f"{analysis_1['category_scores']['certifications']}/10",
                                f"{analysis_1['category_scores']['domain_knowledge']}/15",
                                f"{analysis_1['category_scores']['soft_skills']}/15"
                            ],

                            candidate_2_name: [
                                f"{analysis_2['score']}/100",
                                f"{analysis_2['category_scores']['technical_skills']}/30",
                                f"{analysis_2['category_scores']['experience']}/20",
                                f"{analysis_2['category_scores']['education']}/10",
                                f"{analysis_2['category_scores']['certifications']}/10",
                                f"{analysis_2['category_scores']['domain_knowledge']}/15",
                                f"{analysis_2['category_scores']['soft_skills']}/15"
                            ]
                        }

                        st.dataframe(
                            comparison_data,
                            use_container_width=True,
                            hide_index=True
                        )

                        # ----------------------------------------------
                        # Skills Comparison
                        # ----------------------------------------------

                        st.subheader(
                            "🛠️ Skills Comparison"
                        )

                        skill_col1, skill_col2 = st.columns(2)

                        with skill_col1:

                            st.markdown(
                                f"### {candidate_1_name}"
                            )

                            st.markdown(
                                "**✅ Matched Skills**"
                            )

                            for skill in analysis_1[
                                "matched_skills"
                            ]:

                                st.write(
                                    f"• {skill}"
                                )

                            st.markdown(
                                "**⚠️ Skill Gaps**"
                            )

                            for skill in analysis_1[
                                "missing_skills"
                            ]:

                                st.write(
                                    f"• {skill}"
                                )

                        with skill_col2:

                            st.markdown(
                                f"### {candidate_2_name}"
                            )

                            st.markdown(
                                "**✅ Matched Skills**"
                            )

                            for skill in analysis_2[
                                "matched_skills"
                            ]:

                                st.write(
                                    f"• {skill}"
                                )

                            st.markdown(
                                "**⚠️ Skill Gaps**"
                            )

                            for skill in analysis_2[
                                "missing_skills"
                            ]:

                                st.write(
                                    f"• {skill}"
                                )

                        # ----------------------------------------------
                        # Comparison Result
                        # ----------------------------------------------

                        st.subheader(
                            "🏆 Comparison Result"
                        )

                        score_1 = analysis_1[
                            "score"
                        ]

                        score_2 = analysis_2[
                            "score"
                        ]

                        if score_1 > score_2:

                            difference = (
                                score_1 - score_2
                            )

                            st.success(
                                f"🏆 **{candidate_1_name}** "
                                f"currently ranks higher by "
                                f"**{difference} points**."
                            )

                        elif score_2 > score_1:

                            difference = (
                                score_2 - score_1
                            )

                            st.success(
                                f"🏆 **{candidate_2_name}** "
                                f"currently ranks higher by "
                                f"**{difference} points**."
                            )

                        else:

                            st.info(
                                "Both candidates have "
                                "the same overall score."
                            )
                    # --------------------------------------------------
                    # Top 5 Candidates
                    # --------------------------------------------------

                    st.divider()

                    st.header(
                        "⭐ Top Candidates"
                    )

                    top_candidates = filtered_results[:5]

                    for rank, result in enumerate(
                        top_candidates,
                        start=1
                    ):

                        candidate = result[
                            "candidate"
                        ]

                        analysis = result[
                            "analysis"
                        ]

                        score = analysis[
                            "score"
                        ]

                        eligibility_status = analysis[
                            "eligibility_status"
                        ]

                        with st.expander(
                            f"#{rank} — {candidate} | {score}/100"
                        ):

                            st.subheader(
                                f"🎯 {eligibility_status}"
                            )

                            st.write(
                                analysis["summary"]
                            )

                            # ------------------------------------------
                            # Category Scores
                            # ------------------------------------------

                            st.markdown(
                                "### 📊 Category Scores"
                            )

                            category_scores = analysis[
                                "category_scores"
                            ]

                            score_data = {
                                "Technical Skills":
                                    f"{category_scores['technical_skills']}/30",

                                "Experience":
                                    f"{category_scores['experience']}/20",

                                "Education":
                                    f"{category_scores['education']}/10",

                                "Certifications":
                                    f"{category_scores['certifications']}/10",

                                "Domain Knowledge":
                                    f"{category_scores['domain_knowledge']}/15",

                                "Soft Skills":
                                    f"{category_scores['soft_skills']}/15"
                            }

                            st.table(
                                score_data
                            )

                            # ------------------------------------------
                            # Skills
                            # ------------------------------------------

                            col1, col2 = st.columns(2)

                            with col1:

                                st.markdown(
                                    "### ✅ Matched Skills"
                                )

                                if analysis[
                                    "matched_skills"
                                ]:

                                    for skill in analysis[
                                        "matched_skills"
                                    ]:

                                        st.write(
                                            f"• {skill}"
                                        )

                                else:

                                    st.write(
                                        "No specific matched skills identified."
                                    )

                            with col2:

                                st.markdown(
                                    "### ⚠️ Skill Gaps"
                                )

                                if analysis[
                                    "missing_skills"
                                ]:

                                    for skill in analysis[
                                        "missing_skills"
                                    ]:

                                        st.write(
                                            f"• {skill}"
                                        )

                                else:

                                    st.write(
                                        "No significant skill gaps identified."
                                    )

                            # ------------------------------------------
                            # Strengths
                            # ------------------------------------------

                            st.markdown(
                                "### 💪 Strengths"
                            )

                            for strength in analysis[
                                "strengths"
                            ]:

                                st.write(
                                    f"• {strength}"
                                )

                            # ------------------------------------------
                            # Improvement Suggestions
                            # ------------------------------------------

                            st.markdown(
                                "### 🚀 Improvement Areas"
                            )

                            for suggestion in analysis[
                                "improvement_suggestions"
                            ]:

                                st.write(
                                    f"• {suggestion}"
                                )

                    # --------------------------------------------------
                    # Hiring Recommendation
                    # --------------------------------------------------

                    st.divider()

                    st.header(
                        "💡 Hiring Recommendation"
                    )

                    best_candidate = filtered_results[0]

                    best_analysis = best_candidate[
                        "analysis"
                    ]

                    best_score = best_analysis[
                        "score"
                    ]

                    best_name = best_candidate[
                        "candidate"
                    ]

                    if best_score >= 90:

                        recommendation = (
                            f"**{best_name}** is the strongest "
                            f"candidate based on the current "
                            f"screening results. Their score of "
                            f"**{best_score}/100** indicates strong "
                            f"alignment with the selected role."
                        )

                    elif best_score >= 80:

                        recommendation = (
                            f"**{best_name}** currently ranks "
                            f"highest with a score of "
                            f"**{best_score}/100**. The candidate "
                            f"appears to be a good fit for the "
                            f"selected role."
                        )

                    elif best_score >= 70:

                        recommendation = (
                            f"**{best_name}** ranks highest with "
                            f"**{best_score}/100**. The candidate "
                            f"may be worth further review before "
                            f"proceeding."
                        )

                    else:

                        recommendation = (
                            f"The highest-ranked candidate, "
                            f"**{best_name}**, scored only "
                            f"**{best_score}/100**. Additional "
                            f"manual review is recommended."
                        )

                    st.info(
                        recommendation
                    )
                    # --------------------------------------------------
                    # Download HR Report
                    # --------------------------------------------------

                    st.divider()

                    st.header(
                        "📄 HR Screening Report"
                    )

                    hr_report = generate_hr_report(
                        filtered_results,
                        selected_job
                    )

                    st.download_button(
                        label="⬇️ Download HR Screening Report",
                        data=hr_report,
                        file_name="hr_screening_report.md",
                        mime="text/markdown",
                        use_container_width=True
                    )
    else:

        st.info(
            "Upload two or more candidate resumes "
            "to begin screening."
        )

# --------------------------------------------------
# Run Selected Mode
# --------------------------------------------------

if mode == "👤 Candidate":

    candidate_mode()

elif mode == "🏢 HR":

    hr_mode()