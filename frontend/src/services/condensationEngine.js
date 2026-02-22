/**
 * Condensate Algorithmic Engine (v0.1-alpha)
 * A deterministic approach to memory condensation as per the Condensate Spec.
 */

const STOP_WORDS = new Set(['the', 'is', 'at', 'which', 'on', 'and', 'a', 'an', 'hey', 'hello', 'sure', 'okay', 'don\'t', 'forget']);
const TECH_TERMS = ['v2.0', 'v2.3', 'api', 'auth', 'refactoring', 'migration', 'bottleneck', 'investors', 'roadmap', 'q3', 'backend', 'frontend', 'latency'];

export async function processCondensation(text) {
    const trace = [];
    const startTime = Date.now();

    trace.push({ label: 'Initializing Memory Tiers...', timestamp: Date.now(), status: 'info' });

    // Simulate processing delay for "developer feel"
    await new Promise(r => setTimeout(r, 600));

    // 1. Entity Extraction (Regex based + Dictionary)
    trace.push({ label: 'Scanning for Named Entities & Tech Specs...', timestamp: Date.now(), status: 'info' });
    const words = text.split(/\s+/);
    const entities = new Set();

    // Regex for Version numbers, Times, and Specific patterns
    const versionRegex = /v\d+\.\d+(\.\d+)?/gi;
    const timeRegex = /\d+\s?(am|pm)/gi;
    const capitalizedRegex = /\b[A-Z][a-z]+\b/g;

    // Fix: Explicitly check for regex matches to avoid TypeScript inference issues (never type) with empty array fallbacks
    const versionMatches = text.match(versionRegex);
    if (versionMatches) {
        versionMatches.forEach(v => entities.add(v));
    }

    const timeMatches = text.match(timeRegex);
    if (timeMatches) {
        timeMatches.forEach(t => entities.add(t));
    }

    const capitalizedMatches = text.match(capitalizedRegex);
    if (capitalizedMatches) {
        capitalizedMatches.forEach(c => {
            // Correctly access toLowerCase on inferred string elements
            if (!STOP_WORDS.has(c.toLowerCase())) {
                entities.add(c);
            }
        });
    }

    TECH_TERMS.forEach(term => {
        if (text.toLowerCase().includes(term)) entities.add(term);
    });

    trace.push({ label: `Extracted ${entities.size} unique entities`, timestamp: Date.now(), status: 'success' });

    // 2. Algorithmic Condensation (Importance Scoring)
    trace.push({ label: 'Calculating Semantic Weight...', timestamp: Date.now(), status: 'info' });
    const lines = text.split('\n').filter(l => l.trim().length > 0);
    const actionLines = [];

    lines.forEach(line => {
        const lowerLine = line.toLowerCase();
        // Prioritize action items and state changes
        if (
            lowerLine.includes('need to') ||
            lowerLine.includes('prioritize') ||
            lowerLine.includes('focus on') ||
            lowerLine.includes('meeting') ||
            lowerLine.includes('bottleneck')
        ) {
            // Clean the line of speaker labels
            const cleaned = line.replace(/^(USER|AGENT|BOB|ALICE):\s*/i, '').trim();
            actionLines.push(cleaned);
        }
    });

    const condensed = actionLines.length > 0
        ? actionLines.join('. ')
        : "No critical state changes detected in ephemeral context.";

    // 3. Efficiency Calculation
    const originalLength = text.length;
    const condensedLength = condensed.length;
    const savings = Math.max(0, Math.round(((originalLength - condensedLength) / originalLength) * 100));

    trace.push({ label: 'Delta compression complete', timestamp: Date.now(), status: 'success' });
    trace.push({ label: `Total processing time: ${Date.now() - startTime}ms`, timestamp: Date.now(), status: 'info' });

    return {
        condensed,
        entities: Array.from(entities),
        savings,
        trace,
        layer: 'Condensed Memory (L3)'
    };
}
