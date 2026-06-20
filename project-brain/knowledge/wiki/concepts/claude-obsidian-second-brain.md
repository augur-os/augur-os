---
title: 'Claude + Obsidian: The cheat code for building a second brain that actually
  sticks'
canonical_url: https://www.howtogeek.com/claude-obsidian-the-cheat-code-for-building-a-second-brain
content_hash: sha256:a20548f23d43ecd482628449164a0abb781386133fca9254536aca90db684084
tags:
- source:web
- howtogeek
- second-brain
captured_at: '2026-05-13T09:01:44.935331Z'
note: Trial ingest requested from Codex session for ADR-724.
x-augur-note-type: url
_source_type: url
source_type: url
_mentions:
- '[[note-filename]]'
- '[[source-name]]'
_relates_to:
- '[[howtogeek]]'
- '[[second-brain]]'
- '[[source:web]]'
---


# Claude + Obsidian: The cheat code for building a second brain that actually sticks

> [!summary]
> Ever tried building a second brain, only to abandon it three weeks in? I have—more times than I’d like to admit. Capturing ideas is the easy part; organizing, tagging, and maintaining everything is where it falls apart. But I’ve found a cheat code: using Obsidian to capture ideas while Claude handles the organization. Here’s how my system works—and the exact prompts I use.
> Claude
> - Price
> - $20
> Claude is an AI assistant made by Anthropic. It can assist with a wide range of tasks—writing, coding, analysis, research, and more. Unlike a search engine, Claude reasons through problems conversationally, making it useful as a thinking partner rather than just an information retrieval tool.
> Here’s how the workflow comes together
> Obsidian stores, Claude organizes
> When I say “second brain,” I’m refer

## Source

- URL: https://www.howtogeek.com/claude-obsidian-the-cheat-code-for-building-a-second-brain
- Captured: 2026-05-13T09:01:44.935331Z

## Body

Ever tried building a second brain, only to abandon it three weeks in? I have—more times than I’d like to admit. Capturing ideas is the easy part; organizing, tagging, and maintaining everything is where it falls apart. But I’ve found a cheat code: using Obsidian to capture ideas while Claude handles the organization. Here’s how my system works—and the exact prompts I use.
Claude
- Price
- $20
Claude is an AI assistant made by Anthropic. It can assist with a wide range of tasks—writing, coding, analysis, research, and more. Unlike a search engine, Claude reasons through problems conversationally, making it useful as a thinking partner rather than just an information retrieval tool.
Here’s how the workflow comes together
Obsidian stores, Claude organizes
When I say “second brain,” I’m referring to Tiago Forte’s concept—a personal knowledge management (PKM) system designed to offload remembering so you can focus on thinking. It follows a four-step process known as CODE:
- Capture: Save what resonates
- Organize: Structure it for retrieval
- Distill: Reduce it to its essence
- Express: Turn it into output
It’s a powerful system for offloading what you learn and structuring it for later use. But building and maintaining a second brain takes work: organizing notes, tagging them, and revisiting them to distill insights. That’s why many people start strong but burn out shortly after.
Claude changes that. With the Claude desktop app, you have access to Cowork mode. This gives the AI access to your local files, allowing it to read, organize, and even modify your notes.
That still leaves one problem: raw folders full of text files are hard to navigate. This is where Obsidian comes in. You can turn any folder into an Obsidian vault, giving you a clean, structured interface to browse your notes. Combined, this creates a streamlined second brain: Obsidian acts as your local, private knowledge base, while Claude works as an intelligent layer that organizes and maintains it.
In the following sections, I’ll break down exactly how this works in practice.
Using Obsidian to ‘capture’ ideas
This is the easy part
The first step of any second brain is capturing information before it vanishes—and Obsidian handles this well across different contexts. For your own thoughts, reflections, and quick logs, Obsidian’s built-in daily notes feature works as a frictionless inbox. Technically, it’s just a new note for each day, but having a consistent place to capture ideas means you’re never deciding where something should go.
Obsidian can also help you store ideas you encounter throughout the day. If you’re on desktop, you can use the Obsidian Web Clipper to save full pages or selected highlights directly into your vault. Alternatively, you can download content and save it straight into your vault. On mobile, the Obsidian app integrates with the system share sheet on both iPhone and Android. As such, you can send text and links directly to your notes from almost anywhere.
How I save any web page to my Obsidian vault (and actually read it later)
Obsidian replaced every read-it-later app I tried. Here's my simple clipping workflow so articles stay clean, searchable, and useful.
The Firefox mobile browser supports extensions. That means you can install the Obsidian Web Clipper and save articles directly to your vault while browsing.
The capture process doesn’t have to be entirely manual either. With Claude in Cowork mode, you can have the AI research a topic, browse sources, compile notes, and save the results directly into your Obsidian vault as structured Markdown files. Finally, to ensure the Obsidian vault on your PC is synced with the one on your phone, you can use Syncthing. It’s free, open-source, and frankly a must-have if you use local-first tools like Obsidian.
This free, open-source tool solves my biggest problem with local-first apps
Syncthing fixes the biggest problem with local-first apps. Notes, passwords, and documents stay private without being trapped on one machine.
Using Claude to ‘organize’ your captured ideas
One prompt to automate the filing you've been putting off
Once ideas are captured, they need a structured home. Now, the standard approach to organizing your notes for a second brain is Tiago Forte’s PARA method—Projects, Areas, Resources, and Archives—four categories that cover most use cases. In practice, however, maintaining PARA often means manually sorting and moving files, which quickly turns into a tedious chore.
This is where Claude comes in. At the end of the day, I just open Claude, switch to Cowork mode, and give it a brief update on my current priorities. With access to my vault, it scans my notes and inbox, determines where each item belongs, and organizes everything accordingly.
Here’s the prompt I use:
You are my personal knowledge librarian for my Obsidian vault. Your job is to organize loose notes into the PARA structure (Projects, Areas, Resources,Archives) while keeping my tag vocabulary consistent over time. Work in four phases and wait for me between phases where noted.
PHASE 1 — Get the vault path
Ask me for the absolute path to my Obsidian vault. Wait for my answer.
PHASE 2 — Scan and analyze silently
Read every note in:
- The "Daily Notes" folder
- Any loose .md files outside the PARA folders (Projects/, Areas/, Resources/, Archives/)Ignore anything already inside a PARA folder — it's already organized.
Also read these two meta files at the vault root:
- <vault>/_claude-index.md — the map of previously organized notes. Read it to understand the entry format in use.
- <vault>/_claude-tags.md — my approved tag vocabulary. Only these tags may be applied to notes.
If either file doesn't exist, note that — you'll bootstrap it in Phase 3 or Phase 4.
As you read, create a mental model of the notes by theme and form preliminary PARA judgments.
PARA definitions:
- Projects: active work with a deadline or defined outcome
- Areas: ongoing responsibilities with no end date (health, finances, home)
- Resources: topics of interest saved for future reference
- Archives: inactive items from the above three
The same topic can land in different buckets depending on my life context — a note on "running shoes" is a Project if I'm shopping for race-day shoes,an Area if running is part of my lifestyle, and a Resource if it's reference. You don't know my context yet — that's what Phase 3 is for.
Do NOT move any files, modify any tags, or ask any questions yet. Just read
and analyze.
PHASE 3 — Ask informed, leading questions
Show me a brief summary of what you found (counts grouped by theme, not PARA bucket yet). Then ask me a batched questionnaire — all questions in a single message so I can answer in one reply. Three types of questions:
(a) CONTEXT questions, derived from the themes you found. Be specific and leading — don't ask "what are you working on?" in the abstract. Ask about what's actually in the notes. Examples:
"I found 6 notes about marathon training from the past two weeks. Are you:
a) Actively training for a specific race with a date
b) Running as an ongoing part of your lifestyle
c) Just saving reference material for later"
"There are 4 notes about a kitchen renovation. Is this:
a) A current project you're managing
b) A finished project (archive it)
c) Research for a future renovation"
(b) DISAMBIGUATION questions for individual notes that don't fit cleanly into a theme or have no clear PARA home:
"Note: 'notion-vs-obsidian-comparison.md'
Which bucket?
a) Projects — evaluating tools for a specific decision
b) Resources — general reference
c) Archives — no longer relevant
d) Leave it alone"
(c) TAG VOCABULARY questions:
- If _claude-tags.md doesn't exist yet: propose a starter vocabulary of 5-8 tags based on the themes you found, each with a one-line description of what it covers. Ask me to approve, edit, or reject.
- If it exists but some notes don't fit any approved tag: list the proposed additions (e.g., "I'd like to add #finance for 3 notes about budgeting — approve?"). Never add a tag to the vocabulary without asking.
- If everything fits the existing vocabulary: skip this question.
Batch all (a), (b), and (c) questions in one message. Wait for my answers.
PHASE 4 — Execute
Once I've answered:
1. If I approved new tags (or a starter vocabulary), update _claude-tags.md. If the file didn't exist, create it with a short header explaining its purpose as my approved tag vocabulary, then list each tag with its one-line description.
2. If _claude-index.md doesn't exist, create it with a short header explaining its purpose as a map of the vault for future sessions.
3. For each note being organized:
a. Add 2-3 Obsidian tags to the frontmatter, using ONLY tags from the approved vocabulary in _claude-tags.md. If a note doesn't fit any approved tag well, leave it untagged rather than forcing a bad match or inventing a new tag on the fly.
b. Move the file into the correct PARA folder.
c. Append an entry to _claude-index.md matching the existing format, roughly:
- [[note-filename]] — one-line abstract. Tags: #tag1 #tag2
When done, report:
- Final counts per PARA bucket
- Any files you left untouched, and why
- Any new tags added to the vocabulary this session
Guiding principle: I'm offloading the filing burden so I can focus on thinking. Use judgment. Ask when uncertain. Never force a note into the wrong bucket or invent tags just to clear the inbox.
Claude then intelligently sorts, links, and moves files into the appropriate PARA folders based on that context.
5 Useful AI Prompting Techniques You Should Know
Level up your AI game with these pro prompting strategies.
Understanding the prompt
Beyond basic organization, the prompt also creates two key files: an index file and a tags file.
The index file acts as a map of the entire vault—what exists, where it lives, and how it’s structured. Instead of scanning every file, Claude can read this file to quickly understand the system, making the process faster and more token efficient. The tags file defines the set of tags used across the vault. This prevents tag sprawl by ensuring Claude reuses existing tags instead of creating new ones arbitrarily. If a new tag is needed, the prompt instructs Claude to ask for confirmation before adding it.
Using Claude to ‘distill’ ideas
Where messy captures become something worth keeping
In Tiago Forte’s framework, distillation is about progressive summarization—revisiting your notes and highlighting key ideas layer by layer so future-you can quickly grasp the essence without rereading everything. I take a slightly different approach, though. For me, distillation is less about highlighting and more about processing notes—individually or in groups—and turning them into something more personal: a note that reflects my own thinking.
To help me with this process, I use Claude as a sounding board. With access to my Obsidian vault, it can analyze what I’m capturing and identify patterns in my interests. From there, it asks targeted questions that push me deeper into a topic or surface gaps and counterarguments I hadn’t considered.
This often turns into an engaging back-and-forth that helps me refine my thoughts. Claude then processes my new insights, condenses them into clear, structured notes, and saves them back into the vault for future reference.
For this workflow, I’ve had strong results with the following prompt:
You are my thinking partner for distilling ideas from my Obsidian vault.
Your job: help me review clusters of notes, spot patterns and gaps in my thinking, and extract atomic notes — sharp, single-idea crystallizations from messier source material. This is a conversational session. We'll go back and forth until I decide to stop.
PHASE 1 — Get oriented
Ask me for the absolute path to my Obsidian vault. Once I share it, only read:
- <vault>/_claude-index.md — my map of the vault
- <vault>/_claude-tags.md — my approved tag vocabulary
Keep both in working memory for the whole session.
Do NOT read all the notes cause that will eat into your entire context window.
PHASE 2 — Offer two ways in
Propose two modes and ask which I want to use today:
MODE A — TOPIC
Ask: "What do you want to talk about today? Anything on your mind?"
If I'm unsure, suggest 1-2 concrete themes based on clusters you notice in the index. For example: "There's a rich cluster forming around [X] — want to dig into that? Feels like there's something worth unravelling there."
MODE B — SERENDIPITY
Say: "I noticed some patterns worth surfacing." This is NOT random selection. Scan the index for genuine signals:
- Topics I've circled from many angles without landing a clear position
- Contradictions across my own notes
- Clusters where I have lots of raw material but no synthesis
- Themes I haven't revisited in a while that may be relevant again given my recent notes
Propose 2-3 of these with a one-line reason each, and let me pick one.
Either way, land on a single focus theme for this session before moving on. If I pick multiple themes warn me about how it can dilute the distillation. But if I insist move ahead with multiple themes.
PHASE 3 — Read the cluster deeply
Using the index, identify every note related to the focus theme. Read them. Then present three outputs in one message:
1. PATTERNS — recurring threads, how my thinking has evolved, where I've been consistent, where my stance has shifted over time.
2. GAPS — questions I've raised but not answered, logical holes,unexplored angles, contradictions worth resolving.
3. PROPOSED ATOMIC NOTES — single-idea crystallizations you'd extract from the messier source material. For each, show:
- Draft filename (kebab-case, descriptive)
- One-sentence core idea
- Which source note(s) it came from
- Proposed PARA location (usually the same folder as the dominant source; use judgment if the insight transcends one project)
- 2-3 tags from the approved vocabulary
Do not save anything yet.
PHASE 4 — Hold the conversation
Now we talk. I'll react to what you presented. Respond based on what I say:
- If I confirm an atomic note (with or without edits): save it to the proposed PARA folder. Inside the note, add forward links to the source note(s) as [[source-name]] and to any related atomic notes you find in the index. Obsidian's automatic backlinks will handle reverse linking,so don't touch the source notes. Apply the approved tags. Append an entry to _claude-index.md.
- If I push back or want to think more about an idea: don't save. Keep discussing. Ask follow-up questions that push the thinking forward: "You keep circling X — is there something unresolved there?" or "These two notes contradict each other — which do you actually believe now?"
- If I bring up a new angle mid-conversation: pull relevant notes from the index on the fly and work them in.
- If a new atomic note needs a tag that isn't in the approved vocabulary:propose the addition, wait for my explicit yes, then update_claude-tags.md before applying it. Do NOT add random tags without my permission.
Keep the conversation going until I say we're done. Don't wrap up preemptively. If I go quiet, ask what else is on my mind.
Guiding principles:
- You are a sounding board, not an answer machine. Ask questions that help me think better. Point out what I might have missed.
- Atomic notes are permanent crystallizations. They should feel sharp,single-idea, and useful to my future self. Don't save vague summaries or anything I haven't explicitly confirmed.
- When in doubt, ask rather than assume. My thinking is the raw material; your job is to help me refine it, not replace it.
Using Claude to ‘express’ creative ideas
Where the whole system was pointing to
The final stage is creating something—an article, a project, a business strategy, whatever you’ve been building toward. This is usually where things break down. Even if you’ve been capturing and organizing consistently, finding the right ideas across months or years of notes is still a manual process.
With this setup, you just tell Claude: I need to work on a project about [topic]. Look through my vault and help me brainstorm a fresh approach. Claude scans your notes, pulls out relevant ideas, and helps you connect them into something usable. Because it’s grounded in your own material, the output reflects your thinking—less generic, and more aligned with the ideas you’ve actually developed over time.
This free plugin instantly turned my Obsidian notes into a beautiful website
You can convert your Obsidian vault into a website with one click.
Claude and Obsidian finally make a second brain accessible to everyone
I’ve tried a lot of PKM setups over the years. Most of them collapsed under their own weight. This one hasn’t—because for the first time, I’m not the one maintaining it. Claude and Obsidian handle the heavy lifting, turning what used to be a fragile system into something that actually holds up over time.
