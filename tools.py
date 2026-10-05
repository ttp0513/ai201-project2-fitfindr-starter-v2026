"""
The three FitFindr tools.

Each one is a standalone function you can call and test on its own, before any
of them are wired into the loop. Build and test them one at a time — three
untested tools joined by a loop is one problem that looks like six, because you
can't tell which layer is lying to you.

    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)             → str
    create_fit_card(outfit, new_item)              → str

Their contracts, including typed inputs and empty cases, are documented in the
README Tool Inventory.
"""

import json
import re

import config
from generate import generate
from utils.data_loader import load_listings


# These common words do not describe clothing, so they should not affect a
# listing's search score. For example, "looking for a jacket" becomes "jacket".
_SEARCH_STOP_WORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "looking",
    "me",
    "of",
    "please",
    "show",
    "the",
    "to",
    "want",
    "with",
}


def _keyword_tokens(text: str) -> set[str]:
    """Return normalized search words, treating simple plurals alike."""
    tokens = set()

    # casefold() makes matching case-insensitive. The regex keeps only words
    # and numbers, so punctuation such as commas and hyphens cannot interfere.
    for token in re.findall(r"[a-z0-9]+", text.casefold()):
        if token in _SEARCH_STOP_WORDS:
            continue

        # Normalize simple plurals: "sneakers" and "sneaker" should match.
        # Words ending in "ss" are left alone so "dress" does not become "dres".
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        tokens.add(token)
    return tokens


def _size_matches(requested: str, listed: str) -> bool:
    """Match size options without confusing S with US or L with XL."""
    # Normalize capitalization and repeated spaces before comparing sizes.
    wanted = " ".join(requested.upper().split())
    available = " ".join(listed.upper().split())

    # A letter size must appear as a complete option. This lets M match S/M,
    # while preventing S from matching US 9 and L from matching XL.
    if wanted in {"XXS", "XS", "S", "M", "L", "XL", "XXL"}:
        return re.search(
            rf"(?<![A-Z]){re.escape(wanted)}(?![A-Z])",
            available,
        ) is not None

    # The dataset labels shoe sizes with US. Treat a number such as 8 as US 8.
    if re.fullmatch(r"\d+(?:\.\d+)?", wanted):
        wanted = f"US {wanted}"

    # Compare the complete shoe-size number so US 8 does not match US 8.5.
    shoe_size = re.fullmatch(r"US\s*(\d+(?:\.\d+)?)", wanted)
    if shoe_size:
        listed_shoe_size = re.search(r"\bUS\s*(\d+(?:\.\d+)?)\b", available)
        return bool(
            listed_shoe_size
            and listed_shoe_size.group(1) == shoe_size.group(1)
        )

    # Waist and other sizes use a complete token match. W30 can match the W30
    # portion of W30 L30, but it cannot match part of a different number.
    return re.search(
        rf"(?<![A-Z0-9.]){re.escape(wanted)}(?![A-Z0-9.])",
        available,
    ) is not None


def _listing_text(listing: dict) -> str:
    """Combine the listing fields that a shopper could reasonably search."""
    # brand is often None, while style_tags and colors are lists. Flattening
    # these values gives the keyword scorer one searchable block of text.
    values = [
        listing.get("title"),
        listing.get("description"),
        listing.get("category"),
        *(listing.get("style_tags") or []),
        *(listing.get("colors") or []),
        listing.get("brand"),
        listing.get("platform"),
    ]
    return " ".join(str(value) for value in values if value)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the listings data for items matching a description, and optionally a
    size and a price ceiling.

    This is the tool that doesn't call the model, which makes it the easiest one
    to test and the one to move onto MCP in unit 4.

    Args:
        description: keywords describing what the user wants
                     (e.g. "vintage graphic tee").
        size:        a size string to filter by, or None to skip size filtering.
                     Match case-insensitively — "M" should match "S/M".

                     ⚠️ Read the sizes in the data before you reach for a plain
                     substring test. `"s" in "us 9"` is True, and so is
                     `"l" in "xl"`. A filter that returns shoes when someone
                     asked for a small top reads like a broken search, and it
                     will quietly cost you in unit 4 when you test criterion 1.
                     What counts as a size match is part of your spec — decide
                     it and write it into your Tool Inventory.
        max_price:   maximum price, inclusive, or None to skip price filtering.

    Returns:
        A list of matching listing dicts, best match first.
        **Returns an empty list when nothing matches — an empty list, not None,
        and not an exception.** Your loop branches on this.

    Each listing dict has these fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand (str or None), platform

    Note that `brand` is None for most listings. That is deliberate and
    realistic — thrift listings often have no brand. If something you write
    assumes a brand is always there, you will find out in unit 4.

    Test it from a terminal before you move on:
        python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"
    """
    # Turn the shopper's description into a set of meaningful search words.
    query_tokens = _keyword_tokens(description)
    if not query_tokens:
        # A blank or stop-word-only description cannot produce a useful match.
        return []

    scored_listings = []
    for original_position, listing in enumerate(load_listings()):
        # Apply the two optional filters before spending time scoring keywords.
        # The greater-than comparison makes max_price inclusive.
        if max_price is not None and listing["price"] > max_price:
            continue
        if size is not None and not _size_matches(size, listing["size"]):
            continue

        # A listing's score is the number of unique query words found in it.
        # A zero score means the listing is unrelated and should be removed.
        overlap = query_tokens & _keyword_tokens(_listing_text(listing))
        if overlap:
            scored_listings.append((len(overlap), original_position, listing))

    # Highest scores come first. original_position provides a stable tie-breaker
    # so equal-scoring listings always appear in the same dataset order.
    scored_listings.sort(key=lambda result: (-result[0], result[1]))

    # Remove the internal score data and return only complete listing dicts.
    return [
        listing
        for _, _, listing in scored_listings[: config.SEARCH_RESULT_LIMIT]
    ]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest one or two outfits.

    This one calls the model, through `generate()`. You don't need to think
    about rate limits — the adapter handles pacing for you.

    Args:
        new_item: a listing dict — the item the user is considering.
        wardrobe: a wardrobe dict with an 'items' key holding a list of items.
                  **It may be empty.** Handle that.

    Returns:
        A non-empty string with outfit suggestions.
        With an empty wardrobe, return general styling advice rather than
        raising or returning "". Unit 4 has you trigger the empty wardrobe on
        purpose, so decide now what it should do.

    Test it from a terminal before you move on:
        python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"
    """
    # Using `or []` handles both a missing items key and an explicitly empty list.
    wardrobe_items = wardrobe.get("items") or []

    # JSON keeps every listing field visible to the model and safely represents
    # a missing brand as null instead of assuming that every item has a brand.
    item_details = json.dumps(new_item, ensure_ascii=False, indent=2)

    if wardrobe_items:
        # Give the model readable names and details for pieces the user owns.
        # The prompt tells it to use only these pieces and name them exactly.
        saved_pieces = "\n".join(
            f"- {item.get('name', 'Unnamed item')} "
            f"(category: {item.get('category', 'unknown')}; "
            f"colors: {', '.join(item.get('colors') or []) or 'unknown'}; "
            f"style tags: {', '.join(item.get('style_tags') or []) or 'none'}; "
            f"notes: {item.get('notes') or 'none'})"
            for item in wardrobe_items
        )
        prompt = f"""A shopper is considering this thrift listing:
{item_details}

Their saved wardrobe contains:
{saved_pieces}

Suggest one or two complete, wearable outfits built around the thrift listing.
Use only saved wardrobe pieces shown above, and name each saved piece exactly so
the shopper can find it. Briefly explain why the colors, proportions, or style
work together. Do not write a social-media caption."""
    else:
        # With no saved pieces, ask for general categories instead of allowing
        # the model to pretend the user owns specific wardrobe items.
        prompt = f"""A shopper is considering this thrift listing:
{item_details}

Their saved wardrobe is empty. Suggest one or two complete, wearable ways to
style the item using general clothing categories, colors, and footwear. Make it
clear that these are general styling ideas; do not claim the shopper owns any
specific piece. Do not write a social-media caption."""

    # All external model calls go through generate(), which handles the course
    # project's caching, rate limits, retries, temperature, and usage counting.
    response = generate(
        prompt,
        system=(
            "You are a practical personal stylist. Follow the supplied wardrobe "
            "constraints and return concise plain text."
        ),
    ).strip()
    # Keep the tool's non-empty-string contract even if the model returns blank.
    return response or "No outfit suggestion was generated; please try again."


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Write a short caption someone would actually post about the find.

    This calls the model too.

    Args:
        outfit:   the outfit suggestion string from suggest_outfit().
        new_item: the listing dict for the item.

    Returns:
        A two-to-four sentence caption.
        If `outfit` is empty or whitespace, return a descriptive message rather
        than raising.

    The caption should read like a real post rather than a product description,
    mention the item and its price and platform once each, and be specific about
    the vibe.

    It should also come out **differently for different inputs**. If you run
    this three times on the same item and get three word-for-word identical
    strings, it's one of two things, and both are near the top of `config.py`:

        • CACHE_ENABLED — the adapter handed back an answer it already had
        • TEMPERATURE   — at 0.0 the model gives the same words every time

    Test it from a terminal before you move on:
        python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"
    """
    # Stop before making a paid model call when there is no outfit to describe.
    if not outfit.strip():
        return "A fit card cannot be created without an outfit suggestion."

    # Format one exact price string for the prompt and acceptance criterion.
    price = f"${float(new_item['price']):.2f}"

    # Include the complete record so the caption stays grounded in real data.
    item_details = json.dumps(new_item, ensure_ascii=False, indent=2)
    prompt = f"""Write a social-media-style fit card for this thrift find.

Listing:
{item_details}

Outfit idea:
{outfit}

Requirements:
- Write exactly 2 to 4 complete sentences as one short caption.
- Mention the item naturally.
- Include the exact price string {price} exactly once.
- Include the platform name {new_item['platform']} exactly once.
- Describe a specific vibe and incorporate the outfit idea.
- Do not invent a brand when the listing brand is null.
- Do not use a heading, bullet list, or product-description format."""

    # The system instruction sets the model's role; the prompt above contains
    # the item-specific facts and measurable formatting requirements.
    response = generate(
        prompt,
        system=(
            "You write concise, natural fashion captions and follow factual and "
            "formatting constraints exactly."
        ),
    ).strip()
    # Return a readable fallback instead of breaking the non-empty-string contract.
    return response or "No fit card was generated; please try again."
