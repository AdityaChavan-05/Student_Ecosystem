"""
Branch-specific news categories for Student Ecosystem.

Each branch maps to topics that can be used by the news fetcher
to find relevant engineering and technology news.
"""

BRANCH_MAPPINGS = {
"Computer Science": [
"computer science",
"software development",
"programming",
"cybersecurity",
"cloud computing",
"software engineering",
],

"Artificial Intelligence": [
    "artificial intelligence",
    "machine learning",
    "generative AI",
    "deep learning",
    "robotics",
    "AI research",
],

"Electronics": [
    "electronics engineering",
    "semiconductors",
    "embedded systems",
    "Internet of Things",
    "microelectronics",
    "communication systems",
],

"Mechanical": [
    "mechanical engineering",
    "robotics",
    "automotive engineering",
    "manufacturing technology",
    "3D printing",
    "renewable energy systems",
],

"Civil": [
    "civil engineering",
    "structural engineering",
    "construction technology",
    "sustainable buildings",
    "transportation engineering",
    "smart cities",
],

"Electrical": [
    "electrical engineering",
    "power systems",
    "electric vehicles",
    "renewable energy",
    "smart grids",
    "electrical machines",
],

}

# Additional categories available to all engineering students.

GENERAL_CATEGORIES = [
"engineering research",
"student internships",
"engineering scholarships",
"technical competitions",
"engineering innovation",
]

def get_available_branches():
"""Return the list of supported engineering branches."""
return list(BRANCH_MAPPINGS.keys())

def get_branch_topics(branch: str):
"""
Return topics for a selected branch.

Return an empty list if the branch is not recognized.
"""
if not isinstance(branch, str):
    return []

return BRANCH_MAPPINGS.get(branch.strip(), []).copy()
