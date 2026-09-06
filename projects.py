PROJECTS = [
    {
        "slug": "house-778",
        "name": "House-778",
        "tagline": "A small PHP empire of clone sites nobody asked for.",
        "status": "online",
        "stack": ["PHP", "Hack", "JS"],
        "live_url": "https://house-778.theorangecow.org",
        "source_url": "https://github.com/TheOrangeCow/house-778",
        "screenshots": [],
        "description": [
            "House-778 is a growing collection of clone sites built mostly for the fun of "
            "reverse-engineering how well-known products work under the hood. It currently "
            "includes a Stack Overflow knockoff, a W3Schools knockoff, a Wordle answer checker, "
            "a chat app, and an IT Crowd-themed football quotes page nobody asked for.",
            "Each clone is its own small project sitting behind a shared entry point, which "
            "made it a good excuse to get comfortable with PHP routing, sessions and templating "
            "without a framework doing the heavy lifting.",
        ],
        "features": [
            "Stack Overflow-style Q&A clone with voting",
            "W3Schools-style docs/tutorial clone",
            "Wordle answer checker",
            "Basic chat app",
            "IT Crowd football quotes page",
        ],
    },
    {
        "slug": "library",
        "name": "Library",
        "tagline": "A Flask casino with real-time multiplayer over WebSockets.",
        "status": "online",
        "stack": ["Python", "Flask", "Socket.IO"],
        "live_url": "https://library.theorangecow.org",
        "source_url": "https://github.com/TheOrangeCow/library",
        "screenshots": [],
        "description": [
            "Library is a real-time multiplayer casino built with Flask and Socket.IO. Players "
            "join tables and play Pooheads, Sevens, Blackjack, Poker and Slots against each "
            "other, with chips, leaderboards and in-game chat.",
            "The interesting part was getting game state to sync reliably across multiple "
            "connected clients without everything turning into a race condition - each game "
            "runs its own room and broadcasts state changes over WebSockets rather than relying "
            "on polling.",
        ],
        "features": [
            "Pooheads, Sevens, Blackjack, Poker and Slots",
            "Real-time state sync over Socket.IO",
            "Chip economy and leaderboards",
            "In-game chat per table",
        ],
    },
]


def get_project(slug):
    """Return the project dict matching slug, or None if it doesn't exist."""
    return next((p for p in PROJECTS if p["slug"] == slug), None)
