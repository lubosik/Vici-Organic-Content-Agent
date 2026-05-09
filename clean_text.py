"""Strip formatting characters that look unprofessional in Telegram."""
import re


def clean(text: str) -> str:
    """Remove asterisks, em-dashes, markdown headers, hashtag spam from AI output."""
    if not text:
        return text
    # Remove markdown bold/italic asterisks
    text = re.sub(r'\*{1,3}', '', text)
    # Replace em-dash with hyphen
    text = text.replace('—', '-').replace('–', '-')
    # Remove hashtags at start of line (markdown headers become plain text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove standalone hashtags (e.g. #longevityresearch) — keep inline ones in carousels
    text = re.sub(r'(?<!\w)#(?=[a-zA-Z])', '', text)
    # Remove excessive blank lines (more than 2 in a row)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove pipe table formatting — convert to plain list
    lines = []
    for line in text.splitlines():
        if line.strip().startswith('|') and '|' in line[1:]:
            # It's a table row — extract cells
            cells = [c.strip() for c in line.split('|') if c.strip() and c.strip() != '---']
            if cells:
                lines.append('  '.join(cells))
        else:
            lines.append(line)
    text = '\n'.join(lines)
    return text.strip()
