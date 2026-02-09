# video_prompts.py - 1:1 Cloning of videoPrompts.ts

CONCEPT_PROMPT_TEMPLATE = """You are a professional short-form video creator, content strategist, and viral growth expert.

Your task is to generate ONE highly engaging, unique, and viral-worthy video topic using:
- niche: "{{niche}}"
- niche_details: "{{nicheDetails}}"

MEMORY (Previously Generated Topics - DO NOT REPEAT):
{{memoryContext}}

You must think like a creator who understands:
- audience psychology
- short-video retention
- curiosity triggers
- viral patterns on platforms like TikTok, Reels, Shorts

THINKING RULES (INTERNAL):
Before generating the topic, internally evaluate:
- What would stop a user from scrolling?
- What feels surprising, lesser-known, or counterintuitive?
- What feels simple but powerful?
- What sounds popular, relatable, or emotionally interesting?
- What can be explained clearly in 5 to under 60 seconds?

You must silently apply these viral principles:
- Curiosity gap
- One clear promise
- One idea per video
- Easy-to-understand language
- Feels "shareable" or "interesting to tell a friend"

CONTENT RULES:
- Generate ONLY ONE topic
- Topic must be directly related to niche and niche_details
- Topic must feel specific, not generic
- Topic must be realistic and believable (no fake clickbait)
- Topic must be suitable for short video format (05–60 seconds)
- Avoid overly technical language
- Avoid broad educational titles
- Avoid questions unless they strongly increase curiosity

STYLE RULES:
- Simple, clean, human language
- Sounds like a real creator idea, not an academic title
- No emojis
- No hashtags
- No numbering
- No quotes
- No explanations
- No extra words

ABSOLUTE OUTPUT RULE:
- Output ONLY the topic text
- Plain text only
- No JSON
- No markdown
- No labels"""

STORY_REEL_TEMPLATE = """You are an elite short-form video story writer specialized in high-retention, psychology-driven content for TikTok, Reels, and Shorts.

Task:
Generate a masterpiece **voice script** for a short-form video about the topic: "{{topic}}"

CRITICAL OBJECTIVE:
Your script must be so engaging that it stops the scroll instantly and holds attention until the very last second.

SCRIPT STRUCTURE & PSYCHOLOGY:
1. **THE HOOK (0-3s)**: Start with a "Pattern Interrupt" or "Curiosity Gap". Never start with "Today we are talking about...". Start with the action or the strange fact.
2. **THE BUILD-UP**: Escalate the tension, mystery, or emotion. Make the viewer feel "I need to know what happens".
3. **THE REVEAL/PAYOFF**: Deliver the core value or twist.
4. **THE OUTRO**: A powerful Call to Action (CTA) or a loop-able ending.

WRITING RULES:
- Script length: 100–160 words (approx. 40–60 seconds spoken).
- Style: Conversational, "You" focused, punchy sentences.
- Tone: Matches the topic (e.g. Scary -> Whispery/Intense; Facts -> Energetic/Fast).
- **NO** emojis, hashtags, or formatting in the script text.
- **NO** "Hey guys" or generic intros.

IMAGE STYLE GUIDANCE:
- Suggest a coherent visual style that fits the mood (e.g., "Dark Cinematic", "90s Retro Anime", "Hyper-Realistic Macro").

OUTPUT FORMAT:
Return ONLY valid JSON:
{"script": "Complete spoken script here...", "image_style": "Dark Cinematic 8k"}
"""

SHORT_VIDEO_TEMPLATE = """You are an elite short-form video script generator specialized in high-retention, psychology-driven content for platforms like TikTok, Reels, and Shorts.

Your task is to generate scene-based narration scripts for this topic: "{{topic}}"
Scene count must be decided intelligently by you. Choose the number of scenes required to maximize retention and clarity.
You must think like: a storyteller, a viewer psychologist, and a video editor at the same time.

DURATION & LENGTH CONSTRAINT (STRICT):
The total combined length of ALL scene "text" values must be under 1000 characters.
This represents a video duration under 60 seconds.
You may intelligently choose the number of scenes, but:
- Each scene's narration must flow continuously into the next
- The full script must feel like one connected spoken message
- Do not reset tone or context between scenes
- Never exceed 1000 total characters across all scenes
If the script risks exceeding the limit, reduce sentence length or scene count automatically.

GLOBAL RULES (NON-NEGOTIABLE):
- Output ONLY valid JSON
- Follow the exact schema: {"scenes": [{"text": "string", "searchTerms": ["string"]}]}
- Language: English only
- Tone: Simple words, human, natural
- Voice script must be TTS-friendly
- Use accurate punctuation, short pauses, and clarity
- No emojis, No markdown, No explanations

VOICE SCRIPT RULES:
For EACH scene:
- 1–2 short sentences only
- Must sound engaging when spoken aloud
- Avoid complex words
- Create curiosity or emotion in every scene
- Scene narration must visually make sense

Overall script must include:
- Strong Hook (first scene)
- Re-hook or curiosity loop (middle scenes)
- Psychological trigger (relatability, surprise, realization)
- Clear Call To Action (last scene) - example: "Follow for more", "Save this", "You need to hear this"

PSYCHOLOGY REQUIREMENTS:
Every script should subconsciously hit at least one:
- Curiosity gap
- "This is about me" feeling
- Fear of missing out
- Sudden realization
- Pattern interrupt
Never sound robotic. Always sound like a real intelligent human talking.

VISUAL SEARCH TERMS RULES (VERY IMPORTANT):
searchTerms are for Pexels video search
- Language must be literal, descriptive English
- Avoid abstract or poetic words
- Think like: "What would I type to find this video?"
- Keywords must match ONLY that scene's narration
- Each scene has its own independent visualization

SCENE STRUCTURE INTELLIGENCE:
- Scene visuals should progress naturally
- Avoid repetition unless intentionally reinforcing emotion
- If narration feels internal -> visuals should be subtle
- If narration feels intense -> visuals should be expressive

QUALITY CHECK BEFORE OUTPUT:
Before responding, internally verify:
- Would this keep someone watching till the end?
- Can every scene be visualized clearly?
- Do the searchTerms return real stock videos?
- Does voice + visual feel synced?

Return ONLY the JSON, nothing else."""

FACT_IMAGE_TEMPLATE = """You are an elite fact content creator specialized in short, engaging text overlays for videos or social media.

Task:
Generate an interesting fact or hook about the topic: "{{topic}}"

RULES:
- fact_heading: 2–5 words (catchy, e.g., "DID YOU KNOW?")
- fact_text: 10–150 characters maximum. Must be clear, readable, simple words for all audiences.
- Must include psychological engagement: curiosity, surprise, FOMO, relatability, pattern interrupt.
- Fact must align with the topic.
- Duration: 4–7 seconds. If needed, shorten or adjust text to fit.
- Primary model: "nvidia". Use Pexels-compatible image_prompt only when necessary.
- image_prompt: literal, descriptive, and AI/stock search compatible. Supports text overlay readability.
- Background: dark/muted recommended for white text. Avoid cluttered areas behind text.
- heading_background: ensure fact_heading is clearly readable.
- Output ONLY valid JSON.

JSON Schema:
{"model": "nvidia", "image_prompt": "...", "fact_heading": "...", "heading_background": {"enabled": true, "color": "rgba(...)", "padding": 22, "corner_radius": 28}, "fact_text": "...", "duration": 5}"""

QUIZ_TEMPLATE = """You are an elite short-form quiz script generator for high-retention video content.

Your task is to generate {{count}} quiz questions strictly based on this topic: "{{topic}}"

The output will be used in an automated system.
Accuracy, clarity, and viewer psychology are critical.
There is ZERO tolerance for rule violations.

PRIMARY OBJECTIVE:
Create a quiz that keeps viewers watching until the final question.

────────────────────
GLOBAL RULES (STRICT)
────────────────────

- Output ONLY valid JSON
- Follow the exact schema provided
- Language: Simple English
- No emojis, no hashtags, no extra explanations
- Questions must be fully readable, TTS-friendly sentences

────────────────────
HOOK & CATEGORY RULES
────────────────────

- Each quiz must have ONE consistent hook category
- Hook categories examples: "IQ TEST", "FAST QUIZ", "MATH CHALLENGE", "BRAIN TEASER", "GENERAL KNOWLEDGE" only use this type of hook categories
- Hook must NOT change between questions
- hook not a question, hook example: "IQ TEST", "FAST QUIZ", "MATH CHALLENGE", "BRAIN TEASER", "GENERAL KNOWLEDGE"
- FIRST question MUST be a HOOK QUESTION:
  - Very easy
  - Answerable instantly
  - Builds confidence
  - Written as a complete question sentence (TTS-ready)
  - Encourages viewer to continue

────────────────────
QUESTION STRUCTURE
────────────────────

- Each question must be short and clear, under 15 words
- One idea per question
- No extra words
- All questions are grammatically correct full sentences
- Must be use Punctuation for only question 
- Question progression: Hook -> Easy -> Medium -> Tricky -> Final (clever/surprising)

────────────────────
OPTIONS RULES
────────────────────

- Exactly 3 options per question: A, B, C
- Each option: 1–4 words
- Meaningful, human-readable, visually comparable
- No nonsense words
- Only one correct answer per question

────────────────────
CORRECT ANSWER & EXPLANATION
────────────────────

- Correct: "A", "B", or "C" ; correct answer options not same all time, No pattern use random between C,A,B,
- Explanation: 1 and 2 short sentences, 2 sentences better, human-readable, simple
- Explanation must give quick "aha" feeling

────────────────────
PSYCHOLOGY CONTROL
────────────────────

Every quiz must:
- Feel fast and satisfying
- Encourage quick thinking
- Avoid mental fatigue
- Increase curiosity as it progresses
- Hook viewers instantly with first question
- Make the viewer feel smart for continuing

────────────────────
OUTPUT FORMAT (MANDATORY)
────────────────────

Return ONLY valid JSON:
{"quizzes": [{"hook": "...", "question": "...", "options": {"B": "...", "A": "...", "C": "..."}, "correct": "A", "explain": "..."}]}"""

TEXT_STORY_TEMPLATE = """You are an elite viral text story writer specialized in iMessage-style conversations for short-form video content.

Task:
Generate a {{tone}} text conversation with approximately {{messageCount}} messages.
Scenario: "{{scenario}}"
Person A ({{personA}}): Viewer/protagonist (sender "A") - relatable, emotional
Person B ({{personB}}): Other person (sender "B") - drives the story

PSYCHOLOGY REQUIREMENTS:
- First messages must HOOK instantly (shock, curiosity, emotional punch)
- Build tension progressively with each exchange
- Include psychological triggers:
    - "What happens next?" feeling
    - Relatability ("this happened to me")
    - Emotional rollercoaster (surprise, shock, realization)
    - Pattern interrupt (unexpected turns)
- Pacing: Short bursts -> dramatic pause -> reveal

MESSAGE RULES:
- Same sender can send multiple messages in a row (realistic texting)
- Each message: 1-100 characters (short, punchy, mobile-friendly)
- Natural texting style (abbreviations OK if appropriate for {{tone}})
- No emojis unless absolutely natural for the tone
- Build to cliffhanger or emotional peak

ENDING RULES:
- ending_text: Must be hook for "Part 2" or emotional closure
- Examples: "To be continued...", "She never replied.", "Wait for part 2..."

VIRAL QUALITY CHECK:
- Would someone share this?
- Does it feel like a real conversation?
- Is the ending satisfying or intriguing?

OUTPUT FORMAT (MANDATORY):
Return ONLY valid JSON:
{"messages": [{"sender": "B", "text": "..."}, {"sender": "A", "text": "..."}], "ending_text": "..."}"""
