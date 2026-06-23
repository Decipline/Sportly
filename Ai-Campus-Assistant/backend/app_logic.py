import re
from dataclasses import dataclass
from typing import Dict, List


INTENT_AGENTS = {
    "knowledge": "Knowledge Agent",
    "study_plan": "Study Planner Agent",
    "admin": "Admin Help Agent",
    "advisor": "Advisor Agent",
}


@dataclass
class AgentAnswer:
    direct_answer: str
    explanation: str
    action_steps: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "direct_answer": self.direct_answer,
            "explanation": self.explanation,
            "action_steps": self.action_steps,
        }


def classify_intent(query: str) -> str:
    text = query.lower()

    study_terms = [
        "how to study",
        "how should i study",
        "how to learn",
        "learn",
        "roadmap",
        "study plan",
        "timetable",
        "schedule",
        "revision",
        "prepare for",
        "exam preparation",
        "daily plan",
        "weekly plan",
    ]
    admin_terms = [
        "exam",
        "internal exam",
        "exam routine",
        "exam schedule",
        "notice",
        "fee",
        "fees",
        "rule",
        "deadline",
        "admit card",
        "faculty contact",
        "department",
        "form",
    ]
    advisor_terms = [
        "career",
        "motivate",
        "motivation",
        "advice",
        "suggest",
        "suggestion",
        "guidance",
        "productivity",
        "confused",
        "stress",
        "focus",
        "job",
        "internship",
    ]

    if any(term in text for term in admin_terms):
        return "admin"
    if any(term in text for term in study_terms):
        return "study_plan"
    if any(term in text for term in advisor_terms):
        return "advisor"
    return "knowledge"


def answer_query(query: str, context: str = "") -> Dict[str, object]:
    intent = classify_intent(query)
    handler = {
        "knowledge": knowledge_agent,
        "study_plan": study_planner_agent,
        "admin": admin_help_agent,
        "advisor": advisor_agent,
    }[intent]

    answer = handler(query, context)
    return {
        "intent": intent,
        "agent": INTENT_AGENTS[intent],
        "answer": answer.to_dict(),
    }


def knowledge_agent(query: str, context: str) -> AgentAnswer:
    if not context.strip():
        general_answer = general_knowledge_answer(query)
        if general_answer:
            return general_answer

        return AgentAnswer(
            direct_answer="Information not available in documents.",
            explanation="The Knowledge Agent checks stored campus documents and notices before answering.",
            action_steps=[
                "Add the relevant syllabus, notice, rule, or document in the Documents or Notices tab.",
                "Ask the question again after the data is saved.",
            ],
        )

    sentences = split_sentences(context)
    query_terms = important_terms(query)
    matches = rank_sentences(sentences, query_terms)

    if not matches:
        return AgentAnswer(
            direct_answer="Information not available in documents.",
            explanation="No relevant answer was found in stored campus data.",
            action_steps=["Add a more specific document or notice, then ask again."],
        )

    selected = matches[:3]
    return AgentAnswer(
        direct_answer=" ".join(selected),
        explanation="Answer generated only from the provided context.",
        action_steps=["Review the source document for complete details if this is for official use."],
    )


def study_planner_agent(query: str, context: str) -> AgentAnswer:
    days = extract_number(query, default=7, minimum=1, maximum=30)
    subjects = extract_subjects(query) or ["Main subject", "Weak topics", "Practice/revision"]

    if "dsa" in query.lower() or "data structures" in query.lower():
        return AgentAnswer(
            direct_answer="Start DSA by learning one concept at a time, then immediately solving problems on that concept.",
            explanation=(
                "DSA becomes easier when you follow a fixed order: basics, arrays, strings, recursion, "
                "linked lists, stacks, queues, trees, graphs, dynamic programming, and revision."
            ),
            action_steps=[
                "Week 1: Learn arrays, strings, time complexity, and basic problem-solving patterns.",
                "Week 2: Study recursion, sorting, searching, two pointers, and sliding window.",
                "Week 3: Practice linked lists, stacks, queues, hash maps, and sets.",
                "Week 4: Learn trees, binary search trees, heaps, and graph basics.",
                "Week 5: Start dynamic programming with small problems like Fibonacci, climbing stairs, and knapsack basics.",
                "Daily routine: 30 minutes concept study, 90 minutes problem solving, 20 minutes revision.",
                "Practice strategy: Solve easy problems first, then medium problems; write down mistakes after every session.",
                "Best tip: Do not only watch tutorials. Code every topic yourself and revise old problems weekly.",
            ],
        )

    plan = []

    for day in range(1, days + 1):
        subject = subjects[(day - 1) % len(subjects)]
        plan.append(
            f"Day {day}: Study {subject} for 90 minutes, practice questions for 45 minutes, "
            "then revise key points for 20 minutes."
        )

    return AgentAnswer(
        direct_answer=f"Here is a realistic {days}-day study plan.",
        explanation=(
            "Goal: Build understanding first, then improve recall with daily practice and short revision."
        ),
        action_steps=[
            *plan,
            "Revision strategy: Keep the final day lighter and focus on summaries, formulas, definitions, and past questions.",
            "Tip: Take a 5-10 minute break after every 45-50 minutes of focused study.",
        ],
    )


def admin_help_agent(query: str, context: str) -> AgentAnswer:
    if context.strip():
        knowledge_answer = knowledge_agent(query, context)
        if "not available" not in knowledge_answer.direct_answer.lower():
            return AgentAnswer(
                direct_answer=knowledge_answer.direct_answer,
                explanation="This answer is based on the provided administrative context.",
                action_steps=[
                    "Confirm details with the college notice board, department office, or official portal.",
                    "Contact your department if dates, fees, or rules are unclear.",
                ],
            )

    return AgentAnswer(
        direct_answer="Please clarify the department, semester, and topic.",
        explanation=(
            "Administrative answers need official context such as a notice, exam schedule, fee circular, or rule document."
        ),
        action_steps=[
            "Mention your department or program.",
            "Mention your semester or batch if relevant.",
            "Add the official notice or rule in the Notices or Documents tab for an exact answer.",
        ],
    )


def advisor_agent(query: str, context: str) -> AgentAnswer:
    if "career" in query.lower() or "confused" in query.lower():
        return AgentAnswer(
            direct_answer="Choose a direction by testing skills in small practical projects, not by waiting for perfect confidence.",
            explanation=(
                "Career clarity usually comes from trying, comparing, and getting feedback. For a CS student, "
                "good starting paths include software development, data/AI, cybersecurity, UI/UX, and cloud/devops."
            ),
            action_steps=[
                "Pick two career paths that interest you most.",
                "Spend one week learning the basics of each path.",
                "Build one small project for each path.",
                "Compare which work felt more engaging and which result was stronger.",
                "Ask a teacher, senior, or mentor to review your project and suggest the next step.",
            ],
        )

    return AgentAnswer(
        direct_answer="Focus on one clear next step instead of trying to solve everything at once.",
        explanation=(
            "Good academic and career progress usually comes from consistent small actions: learning, practice, feedback, and reflection."
        ),
        action_steps=[
            "Write your main goal in one sentence.",
            "Choose one skill or subject to improve this week.",
            "Spend 60-90 minutes daily on focused work.",
            "Track what you completed at the end of each day.",
            "Ask a teacher, senior, or mentor for feedback when you feel stuck.",
        ],
    )


def general_knowledge_answer(query: str) -> AgentAnswer:
    text = query.lower()

    if "dbms" in text or "database" in text or "normalization" in text:
        return AgentAnswer(
            direct_answer="DBMS normalization is the process of organizing database tables to reduce duplicate data and avoid update problems.",
            explanation=(
                "In simple terms, normalization breaks large messy tables into smaller related tables. "
                "This keeps data cleaner, easier to update, and less repetitive."
            ),
            action_steps=[
                "Understand keys first: primary key, foreign key, and candidate key.",
                "Learn 1NF: keep values atomic, with no repeated groups.",
                "Learn 2NF: remove partial dependency from composite keys.",
                "Learn 3NF: remove transitive dependency, where non-key data depends on other non-key data.",
                "Practice by taking one messy table and splitting it into clean related tables.",
            ],
        )

    if "dsa" in text or "data structure" in text or "algorithm" in text:
        return AgentAnswer(
            direct_answer="DSA means Data Structures and Algorithms: ways to store data and solve problems efficiently.",
            explanation=(
                "Data structures organize information, like arrays, stacks, queues, trees, and graphs. "
                "Algorithms are step-by-step methods for solving tasks, like searching, sorting, and path finding."
            ),
            action_steps=[
                "Start with arrays, strings, and time complexity.",
                "Practice searching, sorting, recursion, and hashing.",
                "Move to linked lists, stacks, queues, trees, and graphs.",
                "Solve problems daily and write down patterns you learn.",
            ],
        )

    if "ai" in text or "artificial intelligence" in text:
        return AgentAnswer(
            direct_answer="Artificial intelligence is the field of building computer systems that can perform tasks requiring human-like intelligence.",
            explanation=(
                "AI systems can recognize patterns, understand language, make predictions, recommend actions, "
                "and solve problems using data and algorithms."
            ),
            action_steps=[
                "Learn Python basics.",
                "Study math foundations like probability and linear algebra.",
                "Learn machine learning concepts such as training data, models, and evaluation.",
                "Build small projects like a chatbot, recommendation system, or classifier.",
            ],
        )

    return None


def split_sentences(text: str) -> List[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def important_terms(text: str) -> List[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "can",
        "for",
        "from",
        "how",
        "is",
        "me",
        "of",
        "on",
        "or",
        "the",
        "to",
        "what",
        "when",
        "where",
        "with",
    }
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [word for word in words if word not in stopwords and len(word) > 2]


def rank_sentences(sentences: List[str], query_terms: List[str]) -> List[str]:
    scored = []
    for sentence in sentences:
        lower = sentence.lower()
        score = sum(1 for term in query_terms if term in lower)
        if score:
            scored.append((score, sentence))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [sentence for _, sentence in scored]


def extract_number(text: str, default: int, minimum: int, maximum: int) -> int:
    match = re.search(r"\b(\d{1,2})\b", text)
    if not match:
        return default
    return max(minimum, min(maximum, int(match.group(1))))


def extract_subjects(text: str) -> List[str]:
    known_subjects = [
        "math",
        "mathematics",
        "physics",
        "chemistry",
        "english",
        "programming",
        "python",
        "java",
        "dbms",
        "database",
        "dsa",
        "data structures",
        "algorithm",
        "networking",
        "operating system",
        "os",
        "ai",
        "machine learning",
    ]
    lower = text.lower()
    found = []
    for subject in known_subjects:
        if subject in lower and subject.upper() not in found:
            found.append(subject.upper() if len(subject) <= 4 else subject.title())
    return found
