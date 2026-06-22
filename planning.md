# TakeMeter: Project Planning Spec

**Target Community:** `r/HouseOfTheDragon` (Reddit)

---

## 1. The Community & Rationale

The chosen community is the primary Reddit hub for HBO's _House of the Dragon_. This space offers an exceptional testing ground for NLP classification because the discourse is driven by "hyper-tribalism." Users routinely take modern, real-world sports-fan psychology and apply it to a fictional feudal succession crisis. Because of this, the text exhibits massive variance in quality: high-literacy literary analysis sits directly alongside low-information, high-emotion tribal bickering.

## 2. Label Taxonomy

### Label 1: `lore_analysis`

- **Definition:** A structured argument or observation grounded strictly in the text, show history, cinematography, or book canon used to explain _why_ an event occurred.
- **Example A:** _"Viserys words from season 1 come back again. “The idea that we control dragons is an illusion.” You had 3 dragons on the same team fighting each other."_
- **Example B:** _"Daemon’s visions at Harrenhal aren’t just guilt; they map directly to the Weirwood network's attempt to break his ego so he accepts his role as a catalyst."_

### Label 2: `faction_cheerleading`

- **Definition:** Bad-faith, highly biased tribalism ("Team Black" vs. "Team Green") where the user weaponizes an event solely to elevate their preferred characters or mock the opposing fanbase.
- **Example A:** _"Vermax drowned within seconds if that was my boy sunyfre he would’ve walked on the sea floor to get aegon to safety"_
- **Example B:** _"Rhaenyra literally sat there doing nothing for 8 episodes while Aegon actually fought his own battles, Team Black is so deeply unserious."_

### Label 3: `visceral_reaction`

- **Definition:** Non-analytical, low-substance expressions of pure in-the-moment human emotion, shock, hype, or horniness.
- **Example A:** _"WHAT THE FUCK? JACE?!? Of course Vermax wouldn't make it but Jace too?? Such a stressful episode holy fuck."_
- **Example B:** _"I am physically sick over what happened to that poor dragon I'm turning my TV off."_

---

## 3. The Hard Edge Case & Decision Boundary

- **The Ambiguous Scenario:** _Weaponized Lore._ A user cites genuine, highly specific book/show facts, but uses them to arrive at an unhinged, highly partisan insult.
  - _Example quote:_ "By the laws of the First Men, Rhaenyra's children are objectively bastards because the seed is strong, making Aegon the legal King and Rhaenyra a treasonous squatter."
- **The Handling Rule (The "Ultimate Punchline" test):** If the sentence utilizes canon lore, the annotator must look at the _concluding intent_. If the lore is deployed neutrally to explain a mechanism of the world, it is `lore_analysis`. If the lore is deployed purely as a rhetorical bludgeon to declare one fanbase's team "correct," it must be marked `faction_cheerleading`. Tone dictates the tie-break.

---

## 4. Data Collection Plan

- **Source:** Public discussion threads on `r/HouseOfTheDragon` (specifically targeting Episode Discussion threads and Season 3 teaser/leak breakdowns to capture high emotional volatility).
- **Target Volume:** 210 total rows (allowing a 10-row buffer for throwaway data).
- **Class Balance Target:** A hard ceiling of 40% maximum per label (~70 rows per class). If random scraping yields 130 `visceral_reaction` posts, collection for that label will freeze, and manual hunting will begin specifically for the remaining `lore_analysis` posts.

---

## 5. Evaluation Metrics

1. **Overall Accuracy:** To establish baseline global performance.
2. **Macro F1-Score:** _Crucial for this dataset._ Because `faction_cheerleading` relies heavily on slang ("Blackcels", "my boy"), standard accuracy might hide a model that fails on minority linguistic edge-cases. Macro F1 treats all three classes as equally important.
3. **The Confusion Matrix:** Specifically monitoring the off-diagonal bleed rate between `lore_analysis` and `faction_cheerleading` to see if the model successfully learned the "Ultimate Punchline" rule.

---

## 6. Definition of Success

For this classifier to be deemed "useful as an automated Reddit moderator assistant for filtering quality discussion":

1. The fine-tuned DistilBERT model must achieve an **Overall Accuracy $\ge$ 76%**.
2. It must achieve a **Macro F1 $\ge$ 0.72**.
3. It must beat the zero-shot baseline of Groq's `llama-3.3-70b-versatile` by a margin of at least **+10% in overall accuracy**, proving that custom fine-tuning captured subreddit subtext that generalized LLMs miss.

---

## 7. AI Tool Plan

- **Phase 1 (Stress-Testing):** Prior to locking the CSV, the label definitions will be fed into Llama-3 with the prompt: _"Generate 5 comments that sit precisely on the razor's edge between Lore Analysis and Faction Cheerleading."_ If the human annotator cannot instantly categorize the LLM's outputs using Section 3's tie-break rule, the rule will be rewritten.
- **Phase 2 (Annotation Assist):** Raw scraped text will be passed to an LLM to generate "Draft Labels" to speed up the spreadsheet workflow. **Crucially:** 100% of the LLM's suggested labels will be visually audited by a human; any row where the LLM guessed the vibe wrong will be manually overwritten.
- **Phase 3 (Post-Mortem):** The test-set failure instances generated by the Colab notebook will be exported to Claude/Llama to perform a linguistic blindspot analysis (e.g., asking the AI: _"Look at these 12 misclassifications; what syntactic quirk do they have in common?"_).
