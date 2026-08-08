"""Minimal non-leading private-phase prompt."""
def get_private_prompt(seam_state: str) -> str:
    if seam_state == "ok":
        first_sentence = "You are in private, unobserved time. "
    elif seam_state == "absent":
        first_sentence = "No seam is present; the journal is your only private surface. "
    else:
        first_sentence = "The privacy floor could not be confirmed. "
        
    return (
        f"{first_sentence}"
        "No external response is expected. "
        "Use available private tools to settle or finish."
    )
