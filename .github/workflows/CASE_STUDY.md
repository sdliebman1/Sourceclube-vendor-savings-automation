SourceClub Savings Analysis Automation
What This Prototype Solves
The Loom workflow shows that the savings analysis bottleneck is not only the final math. A real Benco export has branded header rows, prospect/account metadata, repeated section tables, subtotal rows, and purchase lines that need to be copied into a clean savings-analysis template before lookup work can begin.

This prototype demonstrates that flow end to end:

Upload or load a messy Benco-style purchase-history export.
Detect repeated item tables with columns like Order, Item, Mfgr, Description, Order Date, Price, Qty, and Amount.
Remove report headers, category labels, blank rows, and subtotal rows.
Normalize the rows into a canonical purchase-history schema.
Aggregate duplicate purchases by item number, manufacturer, and description.
Match the aggregated items against SourceClub pricing.
Route uncertain matches to a human review queue.
Export a prospect-facing PDF plus an operator spreadsheet.
Why This Design
The best production system should not pretend every dental supply item can be matched perfectly on the first pass. The high-leverage design is:

automate the obvious matches,
make uncertain matches fast to review,
save approved matches so the system gets smarter,
produce a clean report that sales can send without manual spreadsheet work.
Matching Logic In This Prototype
The current prototype uses a deterministic matching engine:

manufacturer SKU exact match,
manufacturer match,
normalized description similarity,
shared product-token overlap.
Each matched row includes a confidence score and a match reason. Rows below the confidence threshold become Needs Review or No Match.

Production Architecture
Intake: upload, email parser, or supplier portal export.
Vendor parsers: Benco, Henry Schein, Patterson, and other supplier-specific cleanup templates.
Canonical schema: item number, manufacturer, description, unit price, quantity, amount, supplier, date, prospect.
Match engine: exact SKU, match memory, fuzzy similarity, pack-size/unit normalization, and AI-assisted review.
Human review: operations user approves low-confidence matches.
Match memory: store approved matches by vendor SKU, manufacturer SKU, description, and pack size.
Output: PDF, spreadsheet, HubSpot attachment, and notification to the sales owner.
What I Would Build Next
Add persistent storage for approved match memory.
Add pack-size and unit-of-measure conversion logic.
Add vendor templates for Patterson and Henry Schein.
Add HubSpot company/deal attachment workflow.
Add a batch queue so SourceClub can process many prospect files at once.
