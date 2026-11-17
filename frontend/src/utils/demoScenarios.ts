export const dimensions = ['I', 'D', 'L', 'Cb', 'Ce', 'Cp'] as const;
export type Dimension = typeof dimensions[number];
export const dimensionLabels: Record<Dimension, string> = {
    I: 'Existing property', D: 'Intended use', L: 'Location',
    Cb: 'Building requirements', Ce: 'Energy', Cp: 'Proximity',
};
export interface DemoScenario {
    case_id: string;
    regulatory_use_case: string;
    missing_dimensions: Dimension[];
    conversational: {
        initial_query: string;
        simulated_user_answers_by_dimension: Partial<Record<Dimension, string>>;
    };
    one_shot: { query: string };
    oracle: { query: string };
}

const record = (value: unknown): value is Record<string, unknown> =>
    typeof value === 'object' && value !== null && !Array.isArray(value);
const nonempty = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0;

/** Validate only the demo contract; preserve compatibility with additional research metadata. */
export function parseDemoScenarios(value: unknown): DemoScenario[] {
    if (record(value) && Array.isArray(value.scenarios)) {
        const groupIds = new Set<string>();
        const allVariants: unknown[] = [];
        const activeIds = new Set<string>();
        for (const group of value.scenarios) {
            if (!record(group) || !nonempty(group.id) || groupIds.has(group.id)
                || typeof group.enabled !== 'boolean' || !Array.isArray(group.variants) || group.variants.length === 0) {
                throw new Error('Invalid base scenario: expected unique id, boolean enabled and variants.');
            }
            groupIds.add(group.id);
            for (const variant of group.variants) {
                if (!record(variant) || variant.base_case_id !== group.id) throw new Error('Variant belongs to a different base scenario.');
                allVariants.push(variant);
                if (group.enabled && nonempty(variant.case_id)) activeIds.add(variant.case_id);
            }
        }
        return parseDemoScenarios(allVariants).filter(variant => activeIds.has(variant.case_id));
    }
    if (!Array.isArray(value) || value.length === 0) throw new Error('Expected a non-empty array of scenario triplets.');
    const ids = new Set<string>();
    return value.map((item, index) => {
        const fail = () => { throw new Error(`Invalid scenario at position ${index + 1}. Expected a unique case_id, query triplet, dimensions and answer map.`); };
        if (!record(item)) return fail();
        const conversation = item.conversational;
        if ('enabled' in item
            || !nonempty(item.case_id) || ids.has(item.case_id)
            || !nonempty(item.regulatory_use_case)
            || !Array.isArray(item.missing_dimensions)
            || !item.missing_dimensions.every(d => dimensions.includes(d as Dimension))
            || !record(conversation) || !nonempty(conversation.initial_query)
            || !record(conversation.simulated_user_answers_by_dimension)
            || !Object.entries(conversation.simulated_user_answers_by_dimension).every(([key, answer]) => dimensions.includes(key as Dimension) && nonempty(answer))
            || !record(item.one_shot) || !nonempty(item.one_shot.query)
            || !record(item.oracle) || !nonempty(item.oracle.query)) return fail();
        ids.add(item.case_id);
        return item as unknown as DemoScenario;
    });
}
