# Acceptance criteria — FitFindr

Five criteria that say what "working" means for this agent, written in unit 3
**before** any results existed.

An acceptance criterion names a target: a number, a count, a rate, or something
a person could plainly observe. *"The agent handles errors"* is an opinion.
*"When search returns nothing, the agent stops before calling the second tool,
in 5 of 5 tries"* is a criterion.

Under each one, write a sentence or two on **why that target** and not a
stricter one. A reason that says something about your tools, your loop, or the
data earns credit; *"80% seemed reasonable"* does not.

> Missing your own targets next unit costs you nothing. Setting a target so
> easy you can't miss it does.

**Two are written for you. You write three.**

---

## 1. A matching query completes all three tools

Given a query that matches at least one listing, the agent completes all three
tool calls and returns a fit card — in at least 4 of 5 tries.

**Why this target:**
I picked 4 of 5 because the search only compares words. A user might describe
the right item in a different way, and the two AI-generated responses can also
vary, so expecting a perfect result every time would not be realistic.

---

## 2. An impossible query stops before the second tool

Given a query that matches no listings, the agent stops before calling
`suggest_outfit` and returns a message naming what to change — 5 of 5 tries.

**Why this target:**
I picked 5 of 5 because this is a simple yes-or-no check that does not use AI.
When there are no matches, the agent should always stop; if it continues, the
branch is broken.

---

## 3. The selected listing moves through the session unchanged

Given a query with at least one result, `session["selected_item"]["id"]` equals
`session["search_results"][0]["id"]`, and the `new_item` received by
`suggest_outfit` has that same ID — in 5 of 5 tries.

**Why this target:**

I picked 5 of 5 because the agent should never lose track of the item it chose.
There is no AI guesswork in copying that item forward, so even one changed ID
would mean the session passed along the wrong item.

---

## 4. The fit card includes essential details and stays caption-sized

Given a matching query, the fit card is two to four sentences and includes the
selected item's price and platform — in at least 4 of 5 tries.

**Why this target:**

I picked 4 of 5 because AI-written captions can change from one run to the next
and may occasionally leave out a detail. Four good captions out of five would
still show that the tool usually follows the requested format.

---

## 5. Search always respects the user's maximum price

Given a query with a maximum price, every listing in
`session["search_results"]` has a `price` less than or equal to
`session["parsed"]["max_price"]` — in 5 of 5 tries.

**Why this target:**

I picked 5 of 5 because a user's budget should always be respected. The program
is only comparing prices, so even one item above the limit would mean the filter
is not doing its job.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 4 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath it, like this:

         ## 4. Something about the fit card

         The fit card is different every time.

         **Why this target:** ...

         > **Revised in unit 4:** For 5 different items, the 5 fit cards share
         > no opening sentence.
         >
         > **Why revised:** "different" wasn't checkable — two cards that
         > differed by one word still counted. The new version is something I
         > can actually score.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "I said the empty search stops it 5 of 5 times, but I got 3 of 5,
            so 3 of 5 is more realistic."

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.
     ───────────────────────────────────────────────────────────────────────── -->
