"""Curated first-run content for Student Ecosystem.

Everything here is used as a graceful fallback when live feeds or AI calls are
unavailable. Items are clearly marked as curated in the API responses so the UI
can tell students where the information came from.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from database import (
    count_opportunities,
    create_resource,
    list_resources,
    list_opportunities,
    new_id,
    today,
    upsert_opportunity,
    utcnow,
)

MITWPU_SITE = "https://mitwpu.edu.in/"
MITWPU_LIBRARY = "https://mitwpu.edu.in/library"


def _iso(days: int) -> str:
    return (today() + timedelta(days=days)).isoformat()


def _published(days_ago: int) -> str:
    moment = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return moment.isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Campus guide (fallback when the official website cannot be reached)
# ---------------------------------------------------------------------------

CAMPUS_GUIDE = [
    {
        "id": "campus-exam-window",
        "title": "Mid-semester examination preparation window",
        "category": "Examination",
        "urgency": "high",
        "due_in_days": 12,
        "description": (
            "The mid-semester assessment window is approaching. Confirm your "
            "subject-wise syllabus coverage, lab journal status and seating "
            "instructions with your faculty mentor."
        ),
        "tldr": (
            "Mid-semester assessments are close. Verify your syllabus coverage, "
            "clear pending lab work and confirm the timetable with your mentor."
        ),
        "what_to_do": [
            "Download the subject-wise exam timetable from the student portal.",
            "List topics with less than 70% coverage and block two revision slots.",
            "Complete pending lab journals and get them signed before the window opens.",
        ],
        "tags": ["exams", "academics", "deadline"],
        "link": MITWPU_SITE,
    },
    {
        "id": "campus-assignment-window",
        "title": "Continuous assessment assignment submission",
        "category": "Academic",
        "urgency": "high",
        "due_in_days": 5,
        "description": (
            "Continuous assessment submissions are due through the learning "
            "management portal. Late submissions may attract a grade penalty."
        ),
        "tldr": (
            "A continuous-assessment submission closes in under a week. Upload "
            "the final PDF early and keep a copy of the receipt."
        ),
        "what_to_do": [
            "Rename your file as RollNo_Subject_Assignment.",
            "Upload before the deadline and screenshot the confirmation.",
            "Email the faculty only if the portal fails, with proof attached.",
        ],
        "tags": ["assignments", "submission"],
        "link": MITWPU_SITE,
    },
    {
        "id": "campus-library-hours",
        "title": "Central library extended study hours",
        "category": "Academic",
        "urgency": "normal",
        "due_in_days": None,
        "description": (
            "The central library reading hall stays open later during the "
            "assessment period. Carry your student ID for entry and use the "
            "silent zones for focused revision."
        ),
        "tldr": (
            "Extended library hours are live during assessments. Carry your ID "
            "and reserve group rooms early for project work."
        ),
        "what_to_do": [
            "Carry your MIT-WPU student ID for access.",
            "Book discussion rooms in advance for group revision.",
        ],
        "tags": ["library", "study", "campus"],
        "link": MITWPU_LIBRARY,
    },
    {
        "id": "campus-placement-sessions",
        "title": "Placement and internship readiness sessions",
        "category": "Placement",
        "urgency": "medium",
        "due_in_days": 8,
        "description": (
            "Aptitude drills, resume clinics and mock interviews are running "
            "for pre-final and final year students. Seats are limited and "
            "registration is through the placement cell."
        ),
        "tldr": (
            "Placement readiness sessions open soon with limited seats. Update "
            "your resume and register through the placement cell."
        ),
        "what_to_do": [
            "Update your resume to one page with measurable project impact.",
            "Register for one mock interview slot this week.",
            "Prepare a 90-second introduction for your target role.",
        ],
        "tags": ["placement", "internship", "career"],
        "link": MITWPU_SITE,
    },
    {
        "id": "campus-club-inductions",
        "title": "Student clubs and technical communities induction",
        "category": "Club",
        "urgency": "medium",
        "due_in_days": 10,
        "description": (
            "Coding, robotics, design, entrepreneurship and cultural clubs are "
            "opening inductions for the new cycle. Joining one technical club "
            "is the fastest way to find teammates for hackathons."
        ),
        "tldr": (
            "Club inductions are open. Pick one technical and one creative club "
            "to build a network and find hackathon teammates."
        ),
        "what_to_do": [
            "Shortlist two clubs that match your branch and interests.",
            "Attend one induction session before the form closes.",
            "Introduce yourself in the club community channel.",
        ],
        "tags": ["clubs", "community", "events"],
        "link": MITWPU_SITE,
    },
    {
        "id": "campus-scholarship-docs",
        "title": "Scholarship and fee document verification",
        "category": "Administration",
        "urgency": "medium",
        "due_in_days": 15,
        "description": (
            "Scholarship applicants should complete document verification with "
            "the accounts and scholarship desk. Keep income, category and "
            "bank details ready in the prescribed format."
        ),
        "tldr": (
            "Scholarship verification closes in about two weeks. Assemble your "
            "documents now to avoid last-minute queues."
        ),
        "what_to_do": [
            "Check the scholarship desk notice for the exact document list.",
            "Keep originals plus two photocopies of every document.",
            "Track your application status after submission.",
        ],
        "tags": ["scholarship", "administration", "fees"],
        "link": MITWPU_SITE,
    },
    {
        "id": "campus-hackathon-meetup",
        "title": "Hackathon team-formation meetup at the Innovation Hub",
        "category": "Event",
        "urgency": "high",
        "due_in_days": 3,
        "description": (
            "Find teammates across branches for upcoming national hackathons. "
            "Bring one project idea and a laptop; mentors will help shape the "
            "problem statement and team roles."
        ),
        "tldr": (
            "A team-formation meetup is happening this week. Bring an idea and "
            "leave with a cross-functional team for the next hackathon."
        ),
        "what_to_do": [
            "Write a one-line problem statement you care about.",
            "Prepare a 60-second pitch for your skills and role.",
            "Exchange contacts with at least three potential teammates.",
        ],
        "tags": ["hackathon", "innovation", "teams"],
        "link": MITWPU_SITE,
    },
    {
        "id": "campus-project-review",
        "title": "Semester project review milestone",
        "category": "Academic",
        "urgency": "medium",
        "due_in_days": 21,
        "description": (
            "Project guides will review scope, architecture and progress. "
            "Bring a working demo or wireframes, a task breakdown and a clear "
            "list of blockers."
        ),
        "tldr": (
            "Project review is three weeks out. Lock scope now, assign owners "
            "and prepare a demo rather than only slides."
        ),
        "what_to_do": [
            "Convert your project plan into dated tasks with owners.",
            "Prepare a 5-minute demo script and a fallback recording.",
            "List blockers and ask your guide for one decision per blocker.",
        ],
        "tags": ["projects", "review", "academics"],
        "link": MITWPU_SITE,
    },
    {
        "id": "campus-wellness",
        "title": "Student wellness and mentor connect",
        "category": "Notice",
        "urgency": "normal",
        "due_in_days": 7,
        "description": (
            "Mentor connect and wellness cells are available for academic, "
            "stress and career guidance. Appointments can be booked through "
            "your faculty mentor or the student welfare desk."
        ),
        "tldr": (
            "Mentor connect is open for academic and wellness support. Book a "
            "slot early if you are feeling stretched."
        ),
        "what_to_do": [
            "Book a mentor slot if you feel behind on any subject.",
            "Use the wellness cell for confidential support.",
        ],
        "tags": ["wellness", "mentor", "support"],
        "link": MITWPU_SITE,
    },
    {
        "id": "campus-nptel",
        "title": "NPTEL and SWAYAM credit course registration",
        "category": "Academic",
        "urgency": "medium",
        "due_in_days": 6,
        "description": (
            "Register for NPTEL or SWAYAM courses to earn extra credits and "
            "strengthen your specialization. Check the approved course list "
            "with your department before paying."
        ),
        "tldr": (
            "NPTEL/SWAYAM registrations are open. Confirm department approval "
            "before paying for a course."
        ),
        "what_to_do": [
            "Shortlist two courses aligned with your specialization.",
            "Confirm credit transfer rules with the department office.",
            "Register and add exam dates to your task hub.",
        ],
        "tags": ["nptel", "credits", "courses"],
        "link": "https://nptel.ac.in/",
    },
    {
        "id": "campus-fest-volunteers",
        "title": "Campus fest volunteer applications",
        "category": "Event",
        "urgency": "low",
        "due_in_days": 14,
        "description": (
            "The cultural and sports fest teams are recruiting volunteers for "
            "operations, design, sponsorship and tech support. Volunteering is "
            "a strong addition to your resume."
        ),
        "tldr": (
            "Fest volunteering is open. Pick a role that builds a skill you can "
            "show on your resume."
        ),
        "what_to_do": [
            "Choose one role: tech, design, ops or outreach.",
            "Apply with a short note on relevant experience.",
        ],
        "tags": ["fest", "volunteer", "events"],
        "link": MITWPU_SITE,
    },
    {
        "id": "campus-grievance",
        "title": "Grievance redressal and student support desk",
        "category": "Notice",
        "urgency": "low",
        "due_in_days": None,
        "description": (
            "The student support desk handles academic grievances, document "
            "requests and campus issues. Raise a ticket instead of waiting for "
            "the issue to grow."
        ),
        "tldr": (
            "Student support can resolve academic and document issues. Raise a "
            "tracked ticket with the details attached."
        ),
        "what_to_do": [
            "Collect evidence and dates before raising a ticket.",
            "Follow up once a week with the ticket number.",
        ],
        "tags": ["support", "grievance", "campus"],
        "link": MITWPU_SITE,
    },
]


def get_campus_guide() -> list[dict]:
    """Return campus guide items with dates computed relative to today."""
    items = []
    for index, raw in enumerate(CAMPUS_GUIDE):
        due = raw.get("due_in_days")
        items.append(
            {
                "id": raw["id"],
                "title": raw["title"],
                "link": raw["link"],
                "source": "Student Ecosystem campus guide",
                "description": raw["description"],
                "category": raw["category"],
                "urgency": raw["urgency"],
                "published_at": _published(index),
                "deadline": _iso(due) if due is not None else None,
                "tldr": raw["tldr"],
                "what_to_do": raw["what_to_do"],
                "tags": raw["tags"],
                "curated": True,
                "whats_new": index < 4,
            }
        )
    return items


# ---------------------------------------------------------------------------
# Engineering news fallback
# ---------------------------------------------------------------------------

NEWS_FALLBACK = [
    {
        "title": "Transformers, explained visually — the architecture behind modern AI",
        "link": "https://jalammar.github.io/illustrated-transformer/",
        "source": "Jay Alammar",
        "description": (
            "A visual walkthrough of attention, encoder-decoder blocks and why "
            "transformers replaced recurrent networks across NLP and beyond."
        ),
        "tags": ["AI", "deep learning"],
    },
    {
        "title": "Operating Systems: Three Easy Pieces — the free systems textbook",
        "link": "https://pages.cs.wisc.edu/~remzi/OSTEP/",
        "source": "University of Wisconsin",
        "description": (
            "A free, practical operating systems book covering virtualization, "
            "concurrency and persistence with exercises you can run locally."
        ),
        "tags": ["systems", "core CS"],
    },
    {
        "title": "System Design Primer — learn to design large-scale systems",
        "link": "https://github.com/donnemartin/system-design-primer",
        "source": "GitHub",
        "description": (
            "An open-source guide to scalability, caching, load balancing and "
            "the interview patterns behind large-scale system design rounds."
        ),
        "tags": ["system design", "interviews"],
    },
    {
        "title": "How to read a research paper efficiently",
        "link": "https://web.stanford.edu/class/ee384m/Handouts/HowtoReadPaper.pdf",
        "source": "Stanford University",
        "description": (
            "A classic three-pass method for reading research papers: skim the "
            "structure, understand the claims, then reproduce the results."
        ),
        "tags": ["research", "study skills"],
    },
    {
        "title": "Fast.ai — practical deep learning for coders",
        "link": "https://course.fast.ai/",
        "source": "fast.ai",
        "description": (
            "A free, project-first deep learning course that gets you training "
            "real models in the first lesson without a maths wall."
        ),
        "tags": ["AI", "courses"],
    },
    {
        "title": "The Missing Semester of Your CS Education",
        "link": "https://missing.csail.mit.edu/",
        "source": "MIT",
        "description": (
            "Shell, Git, debugging and tooling skills that CS degrees assume "
            "you picked up on your own. Dense, practical and free."
        ),
        "tags": ["tools", "career"],
    },
    {
        "title": "NPTEL — engineering courses from IITs and IISc",
        "link": "https://nptel.ac.in/",
        "source": "NPTEL",
        "description": (
            "Thousands of certified engineering courses across every branch, "
            "with credit-transfer options through SWAYAM."
        ),
        "tags": ["courses", "credits"],
    },
    {
        "title": "Papers with Code — research plus reproducible implementations",
        "link": "https://paperswithcode.com/",
        "source": "Papers with Code",
        "description": (
            "Find state-of-the-art papers alongside open implementations and "
            "benchmarks so you can learn by running the code."
        ),
        "tags": ["research", "AI"],
    },
]


def get_news_fallback(limit: int = 9) -> list[dict]:
    now = datetime.now(timezone.utc)
    items = []
    for index, raw in enumerate(NEWS_FALLBACK[: max(1, limit)]):
        items.append(
            {
                "id": f"news-fallback-{index}",
                "title": raw["title"],
                "link": raw["link"],
                "source": raw["source"],
                "description": raw["description"],
                "content": raw["description"],
                "published_at": (now - timedelta(hours=index * 5)).isoformat(
                    timespec="seconds"
                ),
                "tags": raw["tags"],
                "fallback": True,
            }
        )
    return items


# ---------------------------------------------------------------------------
# Opportunities radar
# ---------------------------------------------------------------------------

OPPORTUNITY_SEEDS = [
    {
        "id": "opp-sih",
        "title": "Smart India Hackathon",
        "organizer": "Ministry of Education (MoE) Innovation Cell",
        "track": "Hackathon",
        "mode": "Hybrid",
        "location": "India-wide (grand finale in person)",
        "days": 24,
        "duration": 3,
        "prize": "₹1,00,000 per winning team + incubation",
        "perks": "National recognition, ministry problem statements, mentor network",
        "url": "https://www.sih.gov.in/",
        "description": (
            "India's largest open innovation hackathon with real problem "
            "statements from ministries and industry. Teams of six submit a "
            "solution idea, then build during the grand finale."
        ),
        "why": (
            "The strongest resume signal for Indian engineering students: a "
            "national stage, government problem statements and real deployment "
            "potential. Recruiters recognise SIH instantly."
        ),
        "tags": ["national", "team", "innovation"],
        "recurrence_days": 365,
    },
    {
        "id": "opp-ethindia",
        "title": "ETHIndia",
        "organizer": "Devfolio",
        "track": "Hackathon",
        "mode": "In-Person",
        "location": "Bengaluru, India",
        "days": 58,
        "duration": 3,
        "prize": "₹1,00,00,000+ prize pool",
        "perks": "Travel grants, builder mentors, sponsor bounties",
        "url": "https://ethindia.co/",
        "description": (
            "One of the world's largest Ethereum hackathons, with tracks "
            "spanning DeFi, consumer crypto, infrastructure and public goods."
        ),
        "why": (
            "Biggest Web3 builder room in India. Even a non-crypto student can "
            "ship a serious product, meet protocol teams and win bounties."
        ),
        "tags": ["web3", "bounties", "india"],
        "recurrence_days": 365,
    },
    {
        "id": "opp-hackthenorth",
        "title": "Hack the North",
        "organizer": "University of Waterloo",
        "track": "Hackathon",
        "mode": "Hybrid",
        "location": "Waterloo, Canada + online tracks",
        "days": 42,
        "duration": 3,
        "prize": "$50,000+ in prizes",
        "perks": "Travel reimbursement, swag, global mentor network",
        "url": "https://hackthenorth.com/",
        "description": (
            "Canada's largest hackathon with global applicants, sponsor "
            "challenges and a strong beginner track."
        ),
        "why": (
            "A genuinely global hackathon that is friendly to first-timers, "
            "with sponsors that hire from the room."
        ),
        "tags": ["global", "beginner-friendly"],
        "recurrence_days": 365,
    },
    {
        "id": "opp-mlh-ghw",
        "title": "MLH Global Hack Week",
        "organizer": "Major League Hacking",
        "track": "Hackathon",
        "mode": "Online",
        "location": "Remote",
        "days": 6,
        "duration": 7,
        "prize": "Swag, sponsor credits and prizes",
        "perks": "Daily challenges, beginner workshops, global community",
        "url": "https://ghw.mlh.io/",
        "description": (
            "A week of daily build challenges and workshops designed to get "
            "students shipping, no experience required."
        ),
        "why": (
            "The lowest-friction way to start shipping: daily prompts, free "
            "workshops and a certificate you can show."
        ),
        "tags": ["online", "beginner", "weekly"],
        "recurrence_days": 60,
    },
    {
        "id": "opp-gsoc",
        "title": "Google Summer of Code",
        "organizer": "Google Open Source",
        "track": "Open Source",
        "mode": "Online",
        "location": "Remote",
        "days": 88,
        "duration": 84,
        "prize": "$1,500–$6,600 stipend",
        "perks": "Paid mentorship, real OSS commits, global alumni network",
        "url": "https://summerofcode.withgoogle.com/",
        "description": (
            "A paid, remote open-source program where students contribute to "
            "mentoring organizations over 12 weeks."
        ),
        "why": (
            "The single best credential for a software career. You get paid, "
            "mentored and a public contribution history that recruiters trust."
        ),
        "tags": ["paid", "open source", "prestige"],
        "recurrence_days": 365,
    },
    {
        "id": "opp-outreachy",
        "title": "Outreachy Internships",
        "organizer": "Software Freedom Conservancy",
        "track": "Open Source",
        "mode": "Online",
        "location": "Remote",
        "days": 64,
        "duration": 90,
        "prize": "$7,000 stipend",
        "perks": "Mentorship, paid internship, accessibility-first projects",
        "url": "https://www.outreachy.org/",
        "description": (
            "Paid remote internships in open source for people subject to "
            "systemic bias, with a strong mentorship structure."
        ),
        "why": (
            "A paid, highly mentored route into open source with a real stipend "
            "and an inclusive application process."
        ),
        "tags": ["paid", "mentorship", "open source"],
        "recurrence_days": 180,
    },
    {
        "id": "opp-gssoc",
        "title": "GirlScript Summer of Code",
        "organizer": "GirlScript Foundation",
        "track": "Open Source",
        "mode": "Online",
        "location": "Remote",
        "days": 30,
        "duration": 60,
        "prize": "Stipends, swag and certificates",
        "perks": "Beginner-friendly OSS, mentors, leaderboard",
        "url": "https://gssoc.girlscript.tech/",
        "description": (
            "A large open-source program for beginners with mentors, labelled "
            "issues and a contribution leaderboard."
        ),
        "why": (
            "The easiest on-ramp to open source: good-first-issues, responsive "
            "mentors and a public contribution graph."
        ),
        "tags": ["beginner", "open source", "india"],
        "recurrence_days": 365,
    },
    {
        "id": "opp-kaggle",
        "title": "Kaggle Competitions",
        "organizer": "Kaggle (Google)",
        "track": "Contest",
        "mode": "Online",
        "location": "Remote",
        "days": None,
        "duration": 0,
        "prize": "Varies — up to $100,000+",
        "perks": "Public leaderboard, notebooks, medals, hiring visibility",
        "url": "https://www.kaggle.com/competitions",
        "description": (
            "Rolling data science competitions with real datasets, public "
            "leaderboards and community notebooks to learn from."
        ),
        "why": (
            "A ranked, verifiable ML portfolio. Medals are visible to recruiters "
            "and every competition teaches applied modelling fast."
        ),
        "tags": ["ml", "rolling", "portfolio"],
        "recurrence_days": 30,
    },
    {
        "id": "opp-codeforces",
        "title": "Codeforces Rated Rounds",
        "organizer": "Codeforces",
        "track": "Contest",
        "mode": "Online",
        "location": "Remote",
        "days": 2,
        "duration": 1,
        "prize": "Rating, T-shirts and sponsor prizes",
        "perks": "Live rating, editorial, global leaderboard",
        "url": "https://codeforces.com/contests",
        "description": (
            "Short, frequent competitive programming rounds across divisions, "
            "with editorials after every contest."
        ),
        "why": (
            "The fastest feedback loop for DSA. A 1400+ rating is a concrete "
            "signal in internships and placements."
        ),
        "tags": ["dsa", "weekly", "rating"],
        "recurrence_days": 7,
    },
    {
        "id": "opp-icpc",
        "title": "ICPC — International Collegiate Programming Contest",
        "organizer": "ICPC Foundation",
        "track": "Contest",
        "mode": "Hybrid",
        "location": "Regional sites across India",
        "days": 112,
        "duration": 1,
        "prize": "Trophies, travel to world finals",
        "perks": "Team prestige, regional and world finals stage",
        "url": "https://icpc.global/",
        "description": (
            "The oldest and most prestigious university programming contest, "
            "run in three-person teams with regional and world finals."
        ),
        "why": (
            "A world-finals ICPC run is one of the strongest signals in "
            "competitive programming and a story few candidates can match."
        ),
        "tags": ["team", "prestige", "algorithms"],
        "recurrence_days": 365,
    },
    {
        "id": "opp-tcs-codevita",
        "title": "TCS CodeVita",
        "organizer": "Tata Consultancy Services",
        "track": "Contest",
        "mode": "Online",
        "location": "Remote",
        "days": 70,
        "duration": 1,
        "prize": "$10,000+ and direct interview opportunities",
        "perks": "Global ranking, hiring pipeline, certificates",
        "url": "https://codevita.tcsapps.com/",
        "description": (
            "One of the world's largest coding contests, with a global "
            "leaderboard and a direct hiring pathway."
        ),
        "why": (
            "A contest that doubles as a recruitment funnel. A good rank can "
            "convert into an interview at TCS."
        ),
        "tags": ["hiring", "global", "algorithms"],
        "recurrence_days": 365,
    },
    {
        "id": "opp-pune-foss",
        "title": "Pune FOSS Meetup",
        "organizer": "FOSS United Pune",
        "track": "Workshop",
        "mode": "In-Person",
        "location": "Pune, Maharashtra",
        "days": 9,
        "duration": 1,
        "prize": "Free entry",
        "perks": "Talks, networking, open-source maintainers",
        "url": "https://fossunited.org/pune",
        "description": (
            "A local meetup of open-source maintainers, founders and students "
            "with talks and hallway conversations."
        ),
        "why": (
            "A free, local room where you can meet maintainers and find your "
            "first open-source contribution — plus it is in Pune."
        ),
        "tags": ["pune", "local", "free"],
        "recurrence_days": 60,
    },
    {
        "id": "opp-mitwpu-build",
        "title": "MIT-WPU Innovation Hub Build Sprint",
        "organizer": "MIT-WPU Innovation Hub",
        "track": "Hackathon",
        "mode": "In-Person",
        "location": "MIT-WPU, Kothrud, Pune",
        "days": 18,
        "duration": 2,
        "prize": "Campus prizes + incubation support",
        "perks": "Faculty mentors, prototype funding, demo day",
        "url": MITWPU_SITE,
        "description": (
            "A two-day campus build sprint for cross-branch teams working on "
            "campus, sustainability and student-life problems."
        ),
        "why": (
            "Zero travel, campus mentors and a fast prototype you can show in "
            "internship interviews. Perfect first hackathon."
        ),
        "tags": ["pune", "campus", "beginner"],
        "recurrence_days": 120,
    },
    {
        "id": "opp-pycon-india",
        "title": "PyCon India",
        "organizer": "Python Software Foundation India",
        "track": "Summit",
        "mode": "In-Person",
        "location": "India (city rotates)",
        "days": 140,
        "duration": 4,
        "prize": "Conference pass",
        "perks": "Talks, sprints, devsprint, community",
        "url": "https://in.pycon.org/",
        "description": (
            "India's largest Python conference with talks, workshops and a "
            "developer sprint where you contribute to real projects."
        ),
        "why": (
            "A devsprint is the fastest way to land your first merged pull "
            "request, and the talks level up your Python instincts."
        ),
        "tags": ["python", "conference", "sprints"],
        "recurrence_days": 365,
    },
    {
        "id": "opp-fossasia",
        "title": "FOSSASIA Summit",
        "organizer": "FOSSASIA",
        "track": "Summit",
        "mode": "In-Person",
        "location": "Asia (rotating host city)",
        "days": 165,
        "duration": 3,
        "prize": "Conference pass",
        "perks": "Open tech talks, workshops, global community",
        "url": "https://summit.fossasia.org/",
        "description": (
            "A major open-technology summit in Asia covering AI, cloud, "
            "open hardware and public-interest tech."
        ),
        "why": (
            "A genuinely international stage close to home, with strong open "
            "hardware and AI tracks relevant to every branch."
        ),
        "tags": ["global", "open source", "conference"],
        "recurrence_days": 365,
    },
    {
        "id": "opp-unstop",
        "title": "Unstop Competitions & Hiring Challenges",
        "organizer": "Unstop",
        "track": "Contest",
        "mode": "Online",
        "location": "Remote",
        "days": None,
        "duration": 0,
        "prize": "Varies by challenge",
        "perks": "Hiring challenges, case comps, certificates",
        "url": "https://unstop.com/competitions",
        "description": (
            "A rolling calendar of case competitions, coding challenges and "
            "hiring contests from Indian and global companies."
        ),
        "why": (
            "Many of these convert directly into internships. A rolling feed is "
            "the easiest way to always have one challenge in progress."
        ),
        "tags": ["rolling", "hiring", "case comp"],
        "recurrence_days": 30,
    },
    {
        "id": "opp-devfolio",
        "title": "Devfolio Hackathon Calendar",
        "organizer": "Devfolio",
        "track": "Hackathon",
        "mode": "Online",
        "location": "India + remote",
        "days": None,
        "duration": 0,
        "prize": "Varies by hackathon",
        "perks": "Bounties, travel grants, builder community",
        "url": "https://devfolio.co/hackathons",
        "description": (
            "India's busiest hackathon calendar with online and in-person "
            "events, sponsor bounties and beginner tracks."
        ),
        "why": (
            "Always-on hackathon discovery. Filter by online, pick one this "
            "month and you will never have an empty resume section."
        ),
        "tags": ["rolling", "india", "bounties"],
        "recurrence_days": 30,
    },
    {
        "id": "opp-imagine-cup",
        "title": "Microsoft Imagine Cup",
        "organizer": "Microsoft",
        "track": "Hackathon",
        "mode": "Hybrid",
        "location": "Global + regional finals",
        "days": 96,
        "duration": 30,
        "prize": "$100,000+ and Azure credits",
        "perks": "Mentorship, Azure credits, global finals",
        "url": "https://imaginecup.microsoft.com/",
        "description": (
            "A global student startup competition for AI-powered solutions, "
            "with mentorship and Azure credits through the rounds."
        ),
        "why": (
            "The most credible student founder competition: it rewards a real "
            "product, and the Azure credits alone are worth entering."
        ),
        "tags": ["global", "startup", "ai"],
        "recurrence_days": 365,
    },
    {
        "id": "opp-mitacs",
        "title": "Mitacs Globalink Research Internship",
        "organizer": "Mitacs Canada",
        "track": "Fellowship",
        "mode": "In-Person",
        "location": "Canada",
        "days": 126,
        "duration": 90,
        "prize": "Funded research internship",
        "perks": "Stipend, travel support, Canadian lab experience",
        "url": "https://www.mitacs.ca/our-programs/globalink-research-internship-students/",
        "description": (
            "A fully funded 12-week research internship at a Canadian "
            "university for international undergraduates."
        ),
        "why": (
            "A funded international research internship is rare at undergrad "
            "level and a decisive differentiator for higher studies."
        ),
        "tags": ["research", "global", "funded"],
        "recurrence_days": 365,
    },
    {
        "id": "opp-google-ml",
        "title": "Google Machine Learning Crash Course",
        "organizer": "Google",
        "track": "Workshop",
        "mode": "Online",
        "location": "Remote",
        "days": 5,
        "duration": 15,
        "prize": "Free certificate",
        "perks": "Interactive labs, TensorFlow, zero cost",
        "url": "https://developers.google.com/machine-learning/crash-course",
        "description": (
            "Google's free, hands-on ML course with interactive notebooks and "
            "short lessons on core modelling concepts."
        ),
        "why": (
            "A free, structured 15-hour sprint that gives you the vocabulary to "
            "start Kaggle competitions with confidence."
        ),
        "tags": ["free", "ml", "certificate"],
        "recurrence_days": 45,
    },
]


def seed_opportunities() -> int:
    """Insert curated opportunities and roll expired deadlines forward."""
    init_db_needed = count_opportunities()
    if init_db_needed:
        # Roll expired recurring deadlines so the radar never goes stale.
        for item in list_opportunities():
            try:
                recurrence = int(item.get("recurrence_days") or 0)
            except (TypeError, ValueError):
                recurrence = 0
            deadline = item.get("deadline") or ""
            if not recurrence or not deadline or deadline >= today().isoformat():
                continue
            cursor = datetime.fromisoformat(deadline).date()
            while cursor < today():
                cursor += timedelta(days=recurrence)
            item["deadline"] = cursor.isoformat()
            if item.get("starts_at"):
                item["starts_at"] = (cursor + timedelta(days=2)).isoformat()
            upsert_opportunity(item)
        return 0

    created = 0
    for raw in OPPORTUNITY_SEEDS:
        days = raw.get("days")
        deadline = _iso(days) if days is not None else ""
        starts = (
            (today() + timedelta(days=days + 2)).isoformat() if days is not None else ""
        )
        upsert_opportunity(
            {
                "id": raw["id"],
                "title": raw["title"],
                "organizer": raw["organizer"],
                "description": raw["description"],
                "why": raw["why"],
                "track": raw["track"],
                "mode": raw["mode"],
                "location": raw["location"],
                "deadline": deadline,
                "starts_at": starts,
                "prize": raw["prize"],
                "perks": raw["perks"],
                "url": raw["url"],
                "tags": raw["tags"],
                "recurrence_days": raw["recurrence_days"],
                "source": "curated",
            }
        )
        created += 1
    return created


# ---------------------------------------------------------------------------
# Academic vault
# ---------------------------------------------------------------------------

VAULT_SEEDS = [
    # Computer Science core
    {
        "title": "CS50x — Harvard's Introduction to Computer Science",
        "subject": "Programming",
        "branch": "Computer Science",
        "type": "course",
        "url": "https://cs50.harvard.edu/x/",
        "description": "The gold-standard first CS course: C, Python, SQL, Flask and a final project. Free with a verified certificate option.",
        "tags": ["beginner", "harvard", "projects"],
        "starred": 1,
    },
    {
        "title": "Operating Systems: Three Easy Pieces",
        "subject": "Operating Systems",
        "branch": "Computer Science",
        "type": "notes",
        "url": "https://pages.cs.wisc.edu/~remzi/OSTEP/",
        "description": "Free OS textbook covering virtualization, concurrency and persistence with runnable exercises.",
        "tags": ["textbook", "core", "semester 5"],
    },
    {
        "title": "CMU 15-445 Database Systems",
        "subject": "DBMS",
        "branch": "Computer Science",
        "type": "video",
        "url": "https://15445.courses.cs.cmu.edu/",
        "description": "Advanced database internals: storage, indexing, query execution and concurrency. Slides and projects are public.",
        "tags": ["dbms", "advanced", "projects"],
    },
    {
        "title": "NeetCode 150 — structured DSA practice",
        "subject": "Data Structures",
        "branch": "Computer Science",
        "type": "practice",
        "url": "https://neetcode.io/practice",
        "description": "A curated 150-problem DSA roadmap with video explanations, ordered by pattern instead of topic.",
        "tags": ["dsa", "placement", "interview"],
        "starred": 1,
    },
    {
        "title": "The System Design Primer",
        "subject": "System Design",
        "branch": "Computer Science",
        "type": "notes",
        "url": "https://github.com/donnemartin/system-design-primer",
        "description": "Open-source system design guide with diagrams, trade-offs and interview-style case studies.",
        "tags": ["system design", "interviews"],
    },
    {
        "title": "MIT Missing Semester — shell, Git and tooling",
        "subject": "Developer Tools",
        "branch": "All",
        "type": "course",
        "url": "https://missing.csail.mit.edu/",
        "description": "The practical tooling course nobody teaches: shell, scripting, Git, debugging and data wrangling.",
        "tags": ["git", "linux", "career"],
        "starred": 1,
    },
    # AI / ML
    {
        "title": "Fast.ai — Practical Deep Learning for Coders",
        "subject": "Machine Learning",
        "branch": "Artificial Intelligence",
        "type": "course",
        "url": "https://course.fast.ai/",
        "description": "Top-down deep learning: train real models in lesson one, then understand the theory behind them.",
        "tags": ["deep learning", "projects", "free"],
        "starred": 1,
    },
    {
        "title": "Hugging Face NLP & LLM Course",
        "subject": "Machine Learning",
        "branch": "Artificial Intelligence",
        "type": "course",
        "url": "https://huggingface.co/learn",
        "description": "Hands-on transformers, fine-tuning and LLM agents using the Hugging Face ecosystem.",
        "tags": ["llm", "transformers", "hands-on"],
    },
    {
        "title": "Google Machine Learning Crash Course",
        "subject": "Machine Learning",
        "branch": "Artificial Intelligence",
        "type": "course",
        "url": "https://developers.google.com/machine-learning/crash-course",
        "description": "Google's free interactive ML course with TensorFlow labs and short conceptual videos.",
        "tags": ["tensorflow", "free", "certificate"],
    },
    {
        "title": "Kaggle Learn — micro-courses",
        "subject": "Data Science",
        "branch": "Artificial Intelligence",
        "type": "practice",
        "url": "https://www.kaggle.com/learn",
        "description": "Short, practical notebooks on pandas, feature engineering, SQL and intro ML with instant feedback.",
        "tags": ["pandas", "kaggle", "practice"],
    },
    {
        "title": "Papers with Code",
        "subject": "Research",
        "branch": "All",
        "type": "link",
        "url": "https://paperswithcode.com/",
        "description": "Every major ML paper paired with code, datasets and benchmark leaderboards.",
        "tags": ["research", "papers", "benchmarks"],
    },
    # Electronics
    {
        "title": "NPTEL — Basic Electronics",
        "subject": "Electronics",
        "branch": "Electronics",
        "type": "course",
        "url": "https://nptel.ac.in/courses/108106162",
        "description": "Semiconductor devices, diodes, BJTs, op-amps and digital electronics from an IIT professor.",
        "tags": ["nptel", "semester", "core"],
    },
    {
        "title": "All About Circuits — free textbooks",
        "subject": "Electronics",
        "branch": "Electronics",
        "type": "notes",
        "url": "https://www.allaboutcircuits.com/textbook/",
        "description": "Clear, illustrated textbooks on DC/AC circuits, semiconductors and digital logic.",
        "tags": ["circuits", "reference"],
    },
    {
        "title": "Wokwi — browser circuit simulator",
        "subject": "Embedded Systems",
        "branch": "Electronics",
        "type": "tool",
        "url": "https://wokwi.com/",
        "description": "Simulate Arduino, ESP32 and Raspberry Pi circuits in the browser without buying hardware.",
        "tags": ["arduino", "esp32", "simulator"],
    },
    {
        "title": "Arduino Documentation & Tutorials",
        "subject": "Embedded Systems",
        "branch": "Electronics",
        "type": "link",
        "url": "https://docs.arduino.cc/",
        "description": "Official language reference, board guides and project tutorials for embedded prototyping.",
        "tags": ["arduino", "projects"],
    },
    # Mechanical
    {
        "title": "Engineering ToolBox",
        "subject": "Mechanical",
        "branch": "Mechanical",
        "type": "reference",
        "url": "https://www.engineeringtoolbox.com/",
        "description": "Fast reference for material properties, thermodynamics, fluid mechanics and unit conversions.",
        "tags": ["reference", "formulas"],
    },
    {
        "title": "Autodesk Fusion 360 Learning",
        "subject": "CAD",
        "branch": "Mechanical",
        "type": "course",
        "url": "https://www.autodesk.com/learning",
        "description": "Free CAD, CAM and simulation learning paths with student licences for Fusion 360.",
        "tags": ["cad", "fusion360", "design"],
    },
    {
        "title": "MIT 2.007 — Design and Manufacturing",
        "subject": "Design",
        "branch": "Mechanical",
        "type": "video",
        "url": "https://ocw.mit.edu/courses/2-007-design-and-manufacturing-i-spring-2009/",
        "description": "A legendary hands-on design-and-build course with lectures, build notes and competition videos.",
        "tags": ["design", "manufacturing", "mit"],
    },
    # Civil / Electrical
    {
        "title": "NPTEL — Structural Analysis",
        "subject": "Structural Engineering",
        "branch": "Civil",
        "type": "course",
        "url": "https://nptel.ac.in/courses/105101086",
        "description": "Classical structural analysis: determinacy, trusses, deflections and influence lines.",
        "tags": ["structures", "nptel", "core"],
    },
    {
        "title": "NPTEL — Power System Analysis",
        "subject": "Power Systems",
        "branch": "Electrical",
        "type": "course",
        "url": "https://nptel.ac.in/courses/108102047",
        "description": "Load flow, fault analysis, stability and protection for power engineering.",
        "tags": ["power", "nptel", "core"],
    },
    # General academic tooling
    {
        "title": "Overleaf — collaborative LaTeX editor",
        "subject": "Academic Writing",
        "branch": "All",
        "type": "tool",
        "url": "https://www.overleaf.com/",
        "description": "Write reports, papers and resumes in LaTeX with real-time collaboration and templates.",
        "tags": ["latex", "reports", "thesis"],
        "starred": 1,
    },
    {
        "title": "Zotero — reference manager",
        "subject": "Research",
        "branch": "All",
        "type": "tool",
        "url": "https://www.zotero.org/",
        "description": "Collect sources, generate citations and keep your bibliography consistent across reports.",
        "tags": ["citations", "research", "free"],
    },
    {
        "title": "GATE Overflow — previous year questions",
        "subject": "GATE Preparation",
        "branch": "All",
        "type": "practice",
        "url": "https://gateoverflow.in/",
        "description": "Topic-wise GATE questions with community explanations, mock tests and rank discussions.",
        "tags": ["gate", "pyq", "exam"],
    },
    {
        "title": "Striver's SDE Sheet",
        "subject": "Placement Preparation",
        "branch": "All",
        "type": "practice",
        "url": "https://takeuforward.org/strivers-a2z-dsa-course/strivers-a2z-dsa-course-sheet-2/",
        "description": "A structured DSA + core subjects roadmap designed for product-company placement prep.",
        "tags": ["placement", "dsa", "roadmap"],
        "starred": 1,
    },
    {
        "title": "MIT-WPU Central Library",
        "subject": "Campus Resources",
        "branch": "All",
        "type": "link",
        "url": "https://mitwpu.edu.in/library",
        "description": "Institutional access to journals, e-books and reference databases. Use your student login.",
        "tags": ["library", "journals", "campus"],
    },
    {
        "title": "Google Scholar",
        "subject": "Research",
        "branch": "All",
        "type": "link",
        "url": "https://scholar.google.com/",
        "description": "Search peer-reviewed literature, track citations and find open-access versions of papers.",
        "tags": ["research", "papers"],
    },
    {
        "title": "Purdue OWL — academic writing guide",
        "subject": "Academic Writing",
        "branch": "All",
        "type": "reference",
        "url": "https://owl.purdue.edu/owl/purdue_owl.html",
        "description": "Citation formats, report structure and writing guidance for technical papers.",
        "tags": ["writing", "apa", "ieee"],
    },
    {
        "title": "LeetCode — interview practice",
        "subject": "Data Structures",
        "branch": "Computer Science",
        "type": "practice",
        "url": "https://leetcode.com/problemset/",
        "description": "The default problem bank for coding interviews, with company tags and discussion threads.",
        "tags": ["dsa", "interview", "practice"],
    },
]


def seed_vault() -> int:
    """Insert curated academic resources on first run."""
    if list_resources():
        return 0
    created = 0
    for raw in VAULT_SEEDS:
        create_resource(raw)
        created += 1
    return created
