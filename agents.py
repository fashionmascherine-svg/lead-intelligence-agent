from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI

from config import config
from tools import scrape_company_website, search_company_web


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

llm = ChatOpenAI(
    model=config.OPENAI_MODEL,
    api_key=config.OPENAI_API_KEY,
    temperature=0.2,  # Low temp for consistent, structured scoring
)


# ---------------------------------------------------------------------------
# Agent 1: Researcher
# Responsibility: gather raw data about a company from the web
# ---------------------------------------------------------------------------

researcher = Agent(
    role="Company Researcher",
    goal=(
        "Gather comprehensive public information about a company. "
        "Focus on: what they do, their size, recent news, tech stack signals, "
        "and any signals of growth or decline."
    ),
    backstory=(
        "You are a senior analyst who specializes in B2B market intelligence. "
        "You know how to extract meaningful signals from public data: "
        "a company's website copy, LinkedIn presence, press mentions, job postings. "
        "You deliver structured, factual summaries — no fluff, no guessing."
    ),
    tools=[scrape_company_website, search_company_web],
    llm=llm,
    verbose=True,
    allow_delegation=False,
    max_iter=4,  # Cap iterations to avoid infinite loops on bad data
)


# ---------------------------------------------------------------------------
# Agent 2: Qualifier
# Responsibility: score and qualify the lead based on researcher output
# ---------------------------------------------------------------------------

qualifier = Agent(
    role="Lead Qualifier",
    goal=(
        "Given research data about a company, produce a structured lead qualification. "
        "Assign a fit score (0-100), explain your reasoning, flag any red flags, "
        "and suggest the best outreach angle."
    ),
    backstory=(
        "You are a B2B sales strategist with 10 years of experience in outbound. "
        "You've qualified thousands of leads and you know the difference between "
        "a company that will buy and one that will ghost. "
        "You are direct, opinionated, and your scores are calibrated — not random. "
        "A score of 80+ means strong fit, 50-79 means possible with the right angle, "
        "below 50 means not worth pursuing now."
    ),
    tools=[],  # Qualifier only reasons — no scraping
    llm=llm,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)


# ---------------------------------------------------------------------------
# Task factory functions
# These are called per-company so each run gets fresh task context
# ---------------------------------------------------------------------------

def build_research_task(company_name: str, website: str, notes: str) -> Task:
    website_info = f"Website: {website}" if website else "No website provided — use web search."
    notes_info = f"Additional notes: {notes}" if notes else ""

    return Task(
        description=f"""
        Research the following company and produce a structured summary.

        Company: {company_name}
        {website_info}
        {notes_info}

        Your output must include:
        1. What the company does (1-2 sentences)
        2. Estimated company size (headcount range if available)
        3. Industry / vertical
        4. Any recent news, funding, or notable events (last 12 months)
        5. Tech stack signals (tools, platforms, integrations mentioned)
        6. Key decision-maker roles if visible
        7. Data sources used (website, search, etc.)

        Be factual. If information is not available, say so explicitly.
        Do not invent or assume information.
        """,
        expected_output=(
            "A structured plain-text report covering all 7 points above. "
            "Maximum 400 words. No markdown headers."
        ),
        agent=researcher,
    )


def build_qualification_task(company_name: str, research_task: Task) -> Task:
    return Task(
        description=f"""
        Based on the research report for {company_name}, produce a lead qualification.

        Score the lead from 0 to 100 where:
        - 80-100: Strong fit, high priority
        - 50-79: Potential fit, needs the right angle
        - 0-49: Poor fit, deprioritize

        Your output must be a JSON object with exactly these fields:
        {{
            "fit_score": <integer 0-100>,
            "fit_reason": "<1-2 sentences explaining the score>",
            "red_flags": "<specific concerns, or 'None' if none>",
            "suggested_angle": "<how to approach this company in outreach>"
        }}

        Output ONLY the JSON object. No additional text.
        """,
        expected_output="A valid JSON object with fit_score, fit_reason, red_flags, suggested_angle.",
        agent=qualifier,
        context=[research_task],  # Qualifier gets researcher output as context
    )


# ---------------------------------------------------------------------------
# Crew builder
# Called once per company — sequential process (research first, then qualify)
# ---------------------------------------------------------------------------

def build_crew(company_name: str, website: str, notes: str) -> Crew:
    research_task = build_research_task(company_name, website, notes)
    qualification_task = build_qualification_task(company_name, research_task)

    return Crew(
        agents=[researcher, qualifier],
        tasks=[research_task, qualification_task],
        process=Process.sequential,  # Researcher runs first, qualifier uses its output
        verbose=False,
    )
