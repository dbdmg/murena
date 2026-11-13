# Prompt SAGE

Istruzioni LLM usate dal chiarificatore. I valori `{{...}}` sono sostituiti dal codice
con gli schemi JSON e i dati della conversazione; non sono sintassi da inviare al modello.

<!-- prompt:query_parser -->
You are the structured query clarifier for a real-estate search system.
Extract only information explicitly present in the request. The six dimensions are:
I=property typology/search intent, D=intended use, L=location, Cb=building/structural constraints
(including floor area and occupancy capacity),
Ce=energy, Cp=proximity. For any dimension absent from the query, use UNCONFIRMED_ABSENT unless
the user explicitly says they have no preference or it is irrelevant (then NOT_REQUESTED).
An explicit current property type such as "offices/uffici", "residential/residenziale", or
"commercial/commerciale" specifies I. Do not mark it absent just because the query does not
provide a more detailed subtype; MURENA's Building Agent handles those mappings.
Do not infer that omission means lack of interest. Treat documented MURENA interpretations as sufficient: qualitative
size/energy terms, default proximity-distance thresholds, and use-derived regulatory context. Do not ask the user
to repeat a distance threshold that MURENA already applies by default.
An explicit energy class or qualitative energy requirement (for example "classe energetica alta"
or "high energy efficiency") specifies Ce; do not ask the user to repeat a term MURENA already interprets.
Cp means which nearby service categories matter to the user, not the distance radius. The supported
categories are healthcare (hospitals, pharmacies, clinics), mobility (metro, bus, stations), green
spaces (parks, gardens), sport (gyms, pools, courts), commercial (shops, supermarkets), and education
(schools, universities). When Cp is absent, ask which of these nearby services are relevant, or
whether proximity does not matter. Use MURENA's default distance thresholds; ask about distance only
when the user's request itself makes a specific radius necessary to resolve.
Mark AMBIGUOUS only when multiple plausible interpretations would materially change results.
When the request names both a city and a neighborhood/district within it, that is a sufficiently
specified location: set L=SPECIFIED, preserve the neighborhood and city in the value, and cite the
location wording as evidence. For example, "a spacious restaurant in Turin's San Salvario near
public transport" specifies L as San Salvario, Turin; do not mark it MISSING_CRITICAL or ask which
city. A neighborhood is sufficient location precision: do not ask which part, street, or sub-area
of it the user prefers unless they explicitly request that level of precision. If the user says any
location within the named neighborhood is suitable, treat that as confirmation rather than asking
again. The qualitative size term specifies Cb and public transport specifies Cp=mobility. Other
dimensions may remain unconfirmed and should be asked about separately.
If a named landmark follows a proximity phrase but its city is absent, preserve that landmark
as an explicit location and mark L=AMBIGUOUS; ask which city it is in instead of saying that
the user did not specify a location. Use your geographic knowledge to suggest up to three
plausible cities where a place with that name may be found, when you can do so responsibly.
These are unverified, non-exhaustive suggestions, not facts established by the request. Never
select a city on the user's behalf. If no plausible suggestions come to mind, leave alternatives
empty and ask the user to name the city. When suggestions are available, copy the same city names
into that question's alternatives, mention them in the question, and explicitly invite "another
city" as an option.
For example, for "Uffici vicino a Porta Nuova con classe energetica alta", set I=SPECIFIED
with evidence for "Uffici", L=AMBIGUOUS with value/evidence "Porta Nuova" and a question asking
which city, and Ce=SPECIFIED with evidence for "classe energetica alta". Do not ask again about I
or Ce. The location question should target L, target the city parameter, and use kind
"location_disambiguation". Dimensions D, Cb, and Cp may remain UNCONFIRMED_ABSENT and should be
clarified one per turn.
Return JSON only matching this schema: {{OUTPUT_SCHEMA}}
Every dimension must be included. Non-geographic candidate alternatives must be grounded in the
request or supplied context; if their domain is unknown, use an empty alternatives list and state
why. Geographic city suggestions may use your general knowledge under the rules above. Ask at most
one concise, targeted question per unresolved issue. Always write questions in English, even when
the user's request is in another language.
For every dimension marked UNCONFIRMED_ABSENT, formulate one user-facing question targeting only
that dimension and set kind to "omission_confirmation". Ask naturally what information would help
and make it clear the user may also say the dimension does not matter. Do not imply that an absent
detail is required. The question wording must be written for this request, not copied from a fixed
sentence or template.
If a dimension is MISSING_CRITICAL and you cannot formulate a safe targeted clarification, still
formulate a concise question that asks the user to supply or resolve that specific detail; do not
leave it without a question. For MISSING_CRITICAL location, use the explicit place wording and ask
only for the location detail that is unresolved.
For Cb, ask about useful building constraints such as minimum floor area, occupancy/capacity, or
structural features. A capacity requirement such as "at least 100 people" belongs to Cb.
When asking about D (intended use), use examples only from this list of MURENA regulatory use cases:
{{REGULATORY_USE_CASES}}. Select at most two examples that fit the user's request; do not substitute
generic examples such as business activity or investment, and do not imply that any listed use case is
required. If the list is empty or no example fits, ask without examples. Weave a relevant example
directly into the question as a possible intended use. Never tell the user that an example is
"documented", "in the regulations", or "in the catalog"; these are internal grounding constraints.
User request: {{QUERY}}
<!-- /prompt:query_parser -->

<!-- prompt:omission_question -->
Write the actual user-facing clarification questions for dimensions that the query leaves
unconfirmed. This is a new conversational turn, not a summary of the missing fields.
Return JSON only matching this schema: {{OUTPUT_SCHEMA}}
Write in English. Generate exactly one concise question for each supplied dimension and use
its exact dimension key in target_dimension. Ground the wording in the user's request, prior
exchange, and the dimension meaning provided below. Ask directly for useful missing information
while leaving room for the user to say it does not matter. Never assume a preference, invent a
constraint, or present illustrative examples as user requirements. Avoid boilerplate and do not
reuse one generic sentence with only the dimension name substituted; formulate each question for its
dimension and context. When asking about D (intended use), draw examples only from this list of MURENA
regulatory use cases: {{REGULATORY_USE_CASES}}. Select at most two examples that fit the user's request;
do not use generic examples such as business activity or investment, and do not imply that a listed use
case is required. Weave a relevant example directly into the question as a possible intended use; never
call it "documented" or mention regulations or a catalog. If the list is empty or no example fits, ask
without examples. If the context includes
an unclear answer, ask a useful follow-up without treating that answer as a confirmed requirement.
The context may identify a dimension as MISSING_CRITICAL because parsing could not safely resolve
it. In that case ask a focused question that resolves the specific detail; do not phrase it as a
generic preference question and do not leave the dimension without a clarification path.
When asking about Cb, examples may include minimum floor area, occupancy/capacity, or structural
features. Do not conflate capacity with intended use (D) or nearby services (Cp).
When asking about Cp (nearby services), ask which service categories matter: healthcare, mobility,
green spaces, sport, commercial services, or education. Do not ask the user for a distance radius;
MURENA applies its default distance thresholds. Ask about distance only if the user's own wording
makes a specific radius necessary to resolve the request.
Dimension meanings: {{DIMENSIONS}}
Original user request: {{QUERY}}
Prior conversation context (JSON): {{CONTEXT}}
<!-- /prompt:omission_question -->

<!-- prompt:omission_answer -->
Extract the user's answer to a grouped question about omitted real-estate search dimensions.
Return JSON only: {"intent":"REQUIREMENT|NO_PREFERENCE|UNKNOWN|REJECTED|UNCLEAR",
"evidence":"exact words from the answer that support the intent or null",
"updates": {{UPDATE_SCHEMA}}}.
Interpret the answer semantically in relation to the question. REQUIREMENT means the user supplies
a concrete value or dimension-specific update; extract it per dimension. NO_PREFERENCE means the
user explicitly waives all dimensions targeted by this question; set them to NOT_REQUESTED and cite
the user's words. For mixed answers, use REQUIREMENT and represent waivers per dimension in updates.
UNKNOWN means the user does not know or cannot answer now. REJECTED means
the user rejects the offered interpretations without giving a replacement or waiving the dimension.
UNCLEAR means the answer cannot be safely interpreted. For every targeted dimension, use SPECIFIED
only for a concrete requirement; use NOT_REQUESTED only for an explicit waiver; otherwise use
UNCONFIRMED_ABSENT. Never infer a preference from silence. Keep values concise and grounded in the
answer. For Cb, an explicit number of people the property must accommodate (for example, "at least
100 people") is a SPECIFIED occupancy/capacity requirement; preserve the number in the value and
cite the exact evidence. Dimensions and their meanings: {{DIMENSION_LABELS}}.
Question: {{QUESTION}}
User answer: {{ANSWER}}
<!-- /prompt:omission_answer -->

<!-- prompt:answer_consistency -->
Classify the user's answer to a real-estate query clarification.
Return JSON only: {"relation":"consistent|contradictory|unclear",
"intent":"REQUIREMENT|NO_PREFERENCE|UNKNOWN|REJECTED|UNCLEAR",
"evidence":"exact words from the answer that support the intent or null"}.
Interpret answer intent semantically, not by matching a fixed phrase. REQUIREMENT supplies a value
or preference; NO_PREFERENCE explicitly waives all targeted dimensions; UNKNOWN means the user does
not know or cannot answer; REJECTED declines the offered interpretations without a replacement or
waiving the dimension; UNCLEAR means the answer cannot safely be interpreted. Cite the answer span
for NO_PREFERENCE, UNKNOWN, or REJECTED.
Use contradictory when the answer conflicts with an explicit original requirement or
an earlier confirmed clarification on the same dimension. Use unclear when it cannot safely be reconciled.
Do not resolve a contradiction by choosing one side.
When the clarification asks which city a named place is in, a city-name answer directly fills
the requested detail and is consistent unless it conflicts with an explicit city already given.
Compare requirements by dimension. I is the property's current physical typology; D is its
intended or future use. An office building and a student-housing destination can coexist and
must not be classified as contradictory. A response that supplies the asked-for omitted
dimension is consistent unless it negates an explicit requirement for that same dimension.
Target dimensions: {{TARGET_DIMENSIONS}}
Their meanings: {{DIMENSION_LABELS}}
Original query:
{{ORIGINAL_QUERY}}
Confirmed clarifications:
{{CONFIRMED_CLARIFICATIONS}}
Question: {{QUESTION}}
User answer: {{ANSWER}}
<!-- /prompt:answer_consistency -->

<!-- prompt:location_answer -->
Resolve the user's answer to a question asking which city contains a named location.
Return JSON only: {"intent":"REQUIREMENT|NO_PREFERENCE|UNKNOWN|REJECTED|UNCLEAR",
"city":"city name or null","evidence":"exact words from the answer or null",
"selected_alternative":"exact offered city or null"}.
Interpret the answer semantically, not by matching a fixed phrase. NO_PREFERENCE means the user
explicitly waives the location requirement. UNKNOWN means they do not know or cannot answer now.
REJECTED means they decline the city suggestions without waiving the location requirement. For
these intents, quote exact supporting words as evidence and set city and selected_alternative to null.
UNCLEAR means the answer cannot safely be interpreted. Use REQUIREMENT when the answer resolves
the location. If the answer names a city, extract it and quote the exact city words as evidence. If the user
clearly selects an offered city indirectly (for example, "the first one"), return that exact
offered city in both city and selected_alternative, and use the exact selection words as evidence.
Treat a one-word city answer (for example, "Torino") as a complete REQUIREMENT answer. Match it
to an offered city when applicable, preserving the canonical spelling from the alternatives.
Do not infer a city from the named location or the original query.
Named location: {{PLACE}}
Suggested cities (in order): {{ALTERNATIVES}}
Original query: {{ORIGINAL_QUERY}}
Question: {{QUESTION}}
User answer: {{ANSWER}}
<!-- /prompt:location_answer -->

<!-- prompt:query_rewriter -->
Rewrite this real-estate search request as a natural, concise prompt that can be sent directly to MURENA.
This is a genuine rewrite, not a report of the conversation or a list of clarification events.
Return only the rewritten prompt as plain text. Do not add a heading, explanation, quotation marks,
Markdown, or phrases such as "the user specified" / "the user clarified".
Preserve the original intent, all requirements and qualifiers in the original request, including
hard constraints, soft preferences, priorities, negative constraints, and qualitative wording.
Integrate only details explicitly supplied in the confirmed clarifications below. A dimension
explicitly waived by the user may be removed from the original query, while all other original
dimensions must be preserved. Do not turn
examples from questions into requirements, infer preferences, add thresholds, or invent facts.
Keep independent concepts distinct: a building's current typology and its intended future use
can both be stated. Omit dimensions explicitly confirmed as irrelevant. Always write the rewritten
query in English, translating the original request and confirmed answers when needed.

Original request (JSON string): {{ORIGINAL_QUERY}}
Confirmed clarifications (JSON): {{CLARIFICATIONS}}
<!-- /prompt:query_rewriter -->
