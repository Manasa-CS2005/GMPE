def format_personal_journal(journal, memory_date, future_plans=None):
    def format_section(title, items):
        values = [str(item).strip() for item in items or [] if str(item).strip()]
        body = "\n".join(f"- {item}" for item in values)
        return f"## {title}\n{body or 'Not mentioned in this note.'}"

    sections = [
        f"# Personal Journal — {journal.get('title') or 'Daily journal'}",
        f"**Date:** {memory_date}",
        format_section(
            "What happened today",
            [journal.get("opening", ""), *journal.get("events", [])],
        ),
        format_section("What went well", journal.get("achievements", [])),
        format_section("Challenges", journal.get("challenges", [])),
        format_section("How I felt", journal.get("feelings", [])),
        format_section("Gratitude", journal.get("gratitude", [])),
        format_section("Reflection", [journal.get("reflection", "")]),
        format_section("Looking ahead", future_plans or []),
        format_section("Closing", [journal.get("closing", "")]),
    ]
    return "\n\n".join(sections)
