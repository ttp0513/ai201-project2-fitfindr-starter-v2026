"""
The FitFindr planning loop.

This is the file that makes FitFindr an agent rather than a script. It decides
which tool to run next based on what the last one returned.

If your loop calls all three tools no matter what comes back, you have a list
of function calls. A loop looks at the last result before it picks the next
step. **That branch is the graded part of this unit.**

Build and test your three tools in `tools.py` first. Then come here.

    python agent.py          runs both example paths below
"""

import re

import config
import trace
from generate import ModelUnavailable

# search_listings crosses the MCP boundary; the other two tools stay local.
from mcp_client import call_tool
from tools import create_fit_card, suggest_outfit


# Common written size names are converted to the short labels used by the data.
_SIZE_ALIASES = {
    "extra extra small": "XXS",
    "extra small": "XS",
    "small": "S",
    "medium": "M",
    "large": "L",
    "extra large": "XL",
}


def _parse_query(query: str) -> dict:
    """Pull the optional size and budget out of a plain-language request."""
    description = query.strip()

    # Step 1: Find a budget phrase such as "under $30". The captured number is
    # converted to a float because listing prices are stored as numbers.
    price_match = re.search(
        r"\b(?:under|below|up to|max(?:imum)?(?: price)?|less than)\s*"
        r"\$?\s*(\d+(?:\.\d{1,2})?)\b",
        description,
        flags=re.IGNORECASE,
    )
    max_price = float(price_match.group(1)) if price_match else None
    if price_match:
        description = description[:price_match.start()] + description[price_match.end():]

    # Step 2: Find an explicitly labeled size. Sorting the aliases by length
    # ensures "extra large" is checked before the shorter word "large".
    size_words = "|".join(
        sorted((re.escape(name) for name in _SIZE_ALIASES), key=len, reverse=True)
    )
    size_match = re.search(
        rf"\b(?:in\s+)?size\s+({size_words}|xxs|xs|s|m|l|xl|xxl|"
        rf"w\d+(?:\s+l\d+)?|(?:us\s*)?\d+(?:\.\d+)?)\b",
        description,
        flags=re.IGNORECASE,
    )

    size = None
    if size_match:
        written_size = size_match.group(1)
        size = _SIZE_ALIASES.get(
            written_size.casefold(),
            " ".join(written_size.upper().split()),
        )

        # A bare number in a query such as "size 8" refers to a US shoe size in
        # this dataset. Normalize both "8" and "US8" to the stored "US 8" form.
        if re.fullmatch(r"\d+(?:\.\d+)?", size):
            size = f"US {size}"
        elif size.startswith("US"):
            size = f"US {size[2:].strip()}"

        description = description[:size_match.start()] + description[size_match.end():]

    # Step 3: What remains is the item description sent to search_listings.
    # Collapse extra spaces and remove punctuation left around deleted phrases.
    description = re.sub(r"\s+", " ", description).strip(" ,.-")
    return {
        "description": description,
        "size": size,
        "max_price": max_price,
    }


def _record_search_trace(parsed: dict, search_results: list[dict]) -> None:
    """Record the MCP search result and the branch it will cause."""
    if search_results:
        note = (
            f"matches found; first_result_id={search_results[0]['id']}; "
            f"prices={[item['price'] for item in search_results]}; "
            f"max_price={parsed['max_price']}"
        )
    else:
        note = "branch: empty result, stopping"

    trace.step(
        "search_listings (via MCP)",
        inputs=(
            f"description={parsed['description']!r}; "
            f"size={parsed['size']!r}; "
            f"max_price={parsed['max_price']!r}"
        ),
        returned=search_results,
        note=note,
    )


# ── session state ─────────────────────────────────────────────────────────────

def new_session(query: str, wardrobe: dict) -> dict:
    """
    A fresh session for one user interaction.

    The session is the single source of truth for a run. Every tool result goes
    in here, and the next tool reads it back out.

    You could pass values straight from one call to the next. It would work,
    and you would not be able to test it — you can't print a variable you have
    already overwritten. Going through the session is what makes the state
    visible, and unit 4 has you write a criterion about exactly that.

    Add fields if you need them.
    """
    return {
        "query": query,              # what the user typed
        "parsed": {},                # description / size / max_price you pulled out of it
        "search_results": [],        # everything search_listings returned
        "selected_item": None,       # the one you chose — goes into suggest_outfit
        "wardrobe": wardrobe,        # the user's wardrobe
        "outfit_suggestion": None,   # what suggest_outfit returned
        "fit_card": None,            # what create_fit_card returned
        "error": None,               # set when the run ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Run the loop once and return the finished session.

    Args:
        query:    what the user asked for, in plain language
                  (e.g. "vintage graphic tee under $30, size M").
        wardrobe: a wardrobe dict — get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py.

    Returns:
        The session dict. **Check session["error"] first** — if it isn't None,
        the run ended early and the later fields will still be None.

    ─────────────────────────────────────────────────────────────────────────
    HOW THIS LOOP WORKS — follows the branch rule written in Milestone 2.

      1. Start a session with new_session().

      2. Count the times round the loop, and call trace.check_iterations(count)
         on each one before you go again. It raises when the count passes
         MAX_ITERATIONS in config.py — see trace.py.

      3. Parse the query into a description, a size, and a max_price. Regex,
         string splitting, or asking the model are all fine — say which you
         chose in your README. Put the result in session["parsed"].

      4. Call search_listings through MCP with what you parsed.
         Put the results in session["search_results"].

         ⚠️ THIS IS THE BRANCH. If nothing came back:
              - put a message in session["error"] saying what the user could
                change — "No results" is not that message
              - return the session
              - do NOT call suggest_outfit with nothing

      5. Choose an item — the first result is fine. Put it in
         session["selected_item"].

      6. Call suggest_outfit() with the selected item and the wardrobe.
         Put the result in session["outfit_suggestion"].

      7. Call create_fit_card() with the outfit and the item.
         Put the result in session["fit_card"].

      8. Return the session.

    ─────────────────────────────────────────────────────────────────────────
    IN UNIT 4 you come back and add two things:

      • Trace calls. One per step. `trace.step("search_listings", inputs=...,
        returned=...)` — see trace.py. Your README needs the output.

      • A handler for ModelUnavailable, so a bad key produces a message rather
        than a stack trace. The import is already at the top of this file.
    """

    # Every step reads from and writes to this shared session.
    session = new_session(query, wardrobe)

    # Flow: parse → MCP search → stop or select → outfit → fit card.
    next_step = "parse_query"
    iteration_count = 0

    while next_step is not None:
        # Prevent a broken branch from looping forever.
        iteration_count += 1
        trace.check_iterations(iteration_count)

        if next_step == "parse_query":
            # Separate the clothing description from optional size and budget.
            parsed = _parse_query(session["query"])
            session["parsed"] = parsed

            trace.step(
                "parse_query",
                inputs=session["query"],
                returned=(
                    f"description={parsed['description']!r}; "
                    f"size={parsed['size']!r}; "
                    f"max_price={parsed['max_price']!r}"
                ),
            )

            next_step = "search_listings"

        elif next_step == "search_listings":
            # call_tool crosses MCP and returns a normal Python list of dicts.
            parsed = session["parsed"]
            search_results = call_tool(
                "search_listings",
                {
                    "description": parsed["description"],
                    "size": parsed["size"],
                    "max_price": parsed["max_price"],
                },
            )
            session["search_results"] = search_results
            _record_search_trace(parsed, search_results)

            # No item means there is nothing for the later tools to style.
            if not search_results:
                session["error"] = (
                    "No matching listings were found. Try broader item keywords, "
                    "remove the size filter, or increase the maximum price."
                )
                return session

            selected_item = search_results[0]
            session["selected_item"] = selected_item

            trace.step(
                "select_item",
                inputs=f"first_result_id={search_results[0]['id']}",
                returned=selected_item,
                note=f"selected_item_id={selected_item['id']}",
            )

            next_step = "suggest_outfit"

        elif next_step == "suggest_outfit":
            selected_item = session["selected_item"]
            wardrobe = session["wardrobe"]

            outfit_inputs = (
                f"selected_item_id={selected_item['id']}; "
                f"wardrobe_items={len(wardrobe.get('items') or [])}"
            )

            try:
                outfit = suggest_outfit(selected_item, wardrobe)
            except ModelUnavailable as exc:
                session["error"] = (
                    f"Could not create an outfit suggestion. {exc}"
                )
                trace.step(
                    "suggest_outfit",
                    inputs=outfit_inputs,
                    note=f"model unavailable, stopping: {exc}",
                )
                return session

            session["outfit_suggestion"] = outfit

            trace.step(
                "suggest_outfit",
                inputs=outfit_inputs,
                returned=outfit,
            )

            next_step = "create_fit_card"

        elif next_step == "create_fit_card":
            selected_item = session["selected_item"]
            outfit = session["outfit_suggestion"]

            card_inputs = (
                f"selected_item_id={selected_item['id']}; "
                f"outfit_present={bool(outfit)}"
            )

            try:
                fit_card = create_fit_card(outfit, selected_item)
            except ModelUnavailable as exc:
                session["error"] = f"Could not create a fit card. {exc}"
                trace.step(
                    "create_fit_card",
                    inputs=card_inputs,
                    note=f"model unavailable, stopping: {exc}",
                )
                return session

            session["fit_card"] = fit_card

            trace.step(
                "create_fit_card",
                inputs=card_inputs,
                returned=fit_card,
                note="successful run complete",
            )

            next_step = None

        else:
            raise RuntimeError(f"Unknown planning step: {next_step}")

    return session


# ── running it directly ───────────────────────────────────────────────────────

def _show(session: dict) -> None:
    # This is only a user-friendly summary. It deliberately does not print the
    # complete search_results list or its Python type; inspect those separately
    # when verifying the MCP return contract.
    if session["error"]:
        print(f"  stopped: {session['error']}")
        print(f"  fit_card is {session['fit_card']!r} — it should still be None here")
        return

    item = session["selected_item"] or {}
    print(f"  found:    {item.get('title')} — ${item.get('price')} on {item.get('platform')}")
    print(f"  outfit:   {session['outfit_suggestion']}")
    print(f"  fit card: {session['fit_card']}")


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== A query the data can match ===")
    _show(run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    ))

    print("\n=== A query it can't ===")
    _show(run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    ))

    print(
        "\nThe second one should stop before the fit card. If both paths look "
        "the same,\nthe branch isn't doing anything yet."
    )
