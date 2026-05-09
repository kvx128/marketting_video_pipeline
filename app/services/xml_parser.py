"""
xml_parser.py
─────────────
Converts structured Markdown files (client.md, purpose.md) into a single
validated VideoContext XML string that Gemini can consume in one prompt.

Cost: 100% local — zero API calls.
Deps: lxml (installed via requirements.txt)
"""

import os
import re
import logging
from lxml import etree

logger = logging.getLogger(__name__)

# ── DTD lives next to this file ──────────────────────────────────────────────
_DTD_PATH = os.path.join(os.path.dirname(__file__), "video_context.dtd")


def _slugify(header: str) -> str:
    """Convert a Markdown header string to a valid XML tag name.

    Examples:
        'Brand Guidelines' → 'brand_guidelines'
        '# Mission:'       → 'mission'
    """
    slug = header.lstrip("#").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)   # replace non-alphanumeric with _
    slug = slug.strip("_")
    return slug


def _parse_md_to_sub(root: etree._Element, file_path: str, parent_tag: str) -> None:
    """Parse a Markdown file and attach its sections as children of `parent_tag`.

    Markdown structure expected:
        # Section Name
        Content for this section (can span multiple lines)

        ## Subsection (treated identically)
        More content...

    Args:
        root:       The root <VideoContext> XML element.
        file_path:  Absolute or relative path to the .md file.
        parent_tag: XML tag name for the parent element (e.g. 'BrandProfile').

    Raises:
        FileNotFoundError: If the given .md file does not exist.
        ValueError:        If no parseable sections are found in the file.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Markdown file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as fh:
        raw = fh.read()

    # Split on any header line (one or more leading '#' chars)
    # re.split keeps the delimiter when we use a capturing group
    chunks = re.split(r"\n(?=#)", "\n" + raw)
    sections = [c.strip() for c in chunks if c.strip()]

    if not sections:
        raise ValueError(f"No Markdown sections found in: {file_path}")

    parent = etree.SubElement(root, parent_tag)

    for section in sections:
        lines = section.split("\n", 1)
        tag_name = _slugify(lines[0])
        content = lines[1].strip() if len(lines) > 1 else ""

        if not tag_name:
            logger.warning("Skipping section with unresolvable tag in %s", file_path)
            continue

        child = etree.SubElement(parent, tag_name)
        child.text = content
        logger.debug("Added <%s> with %d chars of content", tag_name, len(content))


def md_to_xml_validated(
    client_md_path: str,
    purpose_md_path: str,
    dtd_path: str = _DTD_PATH,
) -> str:
    """Parse two Markdown files into a DTD-validated VideoContext XML string.

    Args:
        client_md_path:  Path to the brand/client Markdown file.
        purpose_md_path: Path to the video intent/purpose Markdown file.
        dtd_path:        Path to the DTD schema file (defaults to sibling DTD).

    Returns:
        A pretty-printed XML string ready to embed in a Gemini prompt.

    Raises:
        FileNotFoundError: If any input file is missing.
        ValueError:        If XML fails DTD validation.
    """
    root = etree.Element("VideoContext")

    _parse_md_to_sub(root, client_md_path, "BrandProfile")
    _parse_md_to_sub(root, purpose_md_path, "VideoIntent")

    # ── DTD Validation ────────────────────────────────────────────────────────
    if not os.path.isfile(dtd_path):
        raise FileNotFoundError(f"DTD schema not found: {dtd_path}")

    with open(dtd_path, "rb") as fh:
        dtd = etree.DTD(fh)

    if not dtd.validate(root):
        errors = dtd.error_log.filter_from_errors()
        error_messages = "\n".join(str(e) for e in errors)
        raise ValueError(
            f"XML validation failed against {dtd_path}:\n{error_messages}\n\n"
            "Ensure your Markdown files have headers matching the DTD tags exactly.\n"
            "Required BrandProfile tags : company_name, mission, vision, products, brand_guidelines\n"
            "Required VideoIntent tags  : intent, duration, dimensions, platform, requirements"
        )

    xml_string = etree.tostring(root, pretty_print=True, encoding="unicode")
    logger.info("VideoContext XML generated successfully (%d bytes)", len(xml_string))
    return xml_string


# ── CLI convenience ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    base = os.path.join(os.path.dirname(__file__), "..", "data")
    client_path  = os.path.join(base, "client.md")
    purpose_path = os.path.join(base, "purpose.md")

    try:
        xml = md_to_xml_validated(client_path, purpose_path)
        print(xml)
        sys.exit(0)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
