/**
 * Struttura di una condizione SQL tipizzata e ricorsiva
 */
export interface SqlCondition {
    operator: 'AND' | 'OR' | null;
    content?: string;
    children?: SqlCondition[];
}

/**
 * Parses a SQL WHERE clause and extracts individual conditions recursively.
 */
export const parseSqlWhereConditions = (sqlQuery: string): SqlCondition[] => {
    if (!sqlQuery) return [];

    // Normalize spaces and newlines
    const cleanSql = sqlQuery.replace(/\s+/g, ' ').trim();

    let whereClause = '';

    // Extract WHERE part
    if (cleanSql.toUpperCase().includes('SELECT')) {
        const whereMatch = cleanSql.match(/WHERE\s+(.*?)(\s+(?:GROUP BY|ORDER BY|LIMIT|OFFSET)|$)/i);
        if (whereMatch && whereMatch[1]) {
            whereClause = whereMatch[1];
        } else {
            return [{ operator: null, content: 'Nessun filtro specifico applicato (Query Globale)' }];
        }
    } else {
        whereClause = cleanSql.replace(/^WHERE\s+/i, '');
    }

    return parseRecursive(whereClause, null);
};

/**
 * Helper function for recursive parsing
 */
const parseRecursive = (clause: string, initialOperator: 'AND' | 'OR' | null): SqlCondition[] => {
    const tokens: string[] = [];
    const operators: ('AND' | 'OR')[] = [];

    let current = '';
    let parenthesisCount = 0;
    let betweenCount = 0;
    let inQuote = false;
    let quoteChar = '';

    const pushToken = () => {
        let clean = current.trim();
        if (clean) {
            tokens.push(clean);
        }
        current = '';
    };

    for (let i = 0; i < clause.length; i++) {
        const char = clause[i];

        if ((char === "'" || char === '"') && clause[i - 1] !== '\\') {
            if (!inQuote) {
                inQuote = true;
                quoteChar = char;
            } else if (char === quoteChar) {
                inQuote = false;
            }
        }

        if (!inQuote) {
            if (char === '(') parenthesisCount++;
            if (char === ')') parenthesisCount--;
        }

        if (!inQuote && parenthesisCount === 0) {
            const sub = clause.substring(i).toUpperCase();

            // Check for BETWEEN to avoid splitting its AND
            if (sub.startsWith(' BETWEEN ')) {
                betweenCount++;
                current += clause.substring(i, i + 9);
                i += 8;
                continue;
            } else if (sub.startsWith('BETWEEN ')) {
                betweenCount++;
                current += clause.substring(i, i + 8);
                i += 7;
                continue;
            }

            if (sub.startsWith(' AND ')) {
                if (betweenCount > 0) {
                    betweenCount--;
                    current += clause.substring(i, i + 5);
                    i += 4;
                    continue;
                } else {
                    pushToken();
                    operators.push('AND');
                    i += 4;
                    continue;
                }
            } else if (sub.startsWith(' OR ')) {
                pushToken();
                operators.push('OR');
                i += 3;
                continue;
            }
        }
        current += char;
    }
    pushToken();

    const result: SqlCondition[] = [];

    tokens.forEach((token, idx) => {
        const operator = idx === 0 ? initialOperator : operators[idx - 1];
        const stripped = stripOuterParentheses(token);

        // Filter out technical/spatial conditions
        const isTechnicalAction = /latitudine|longitudine|haversine_km/i.test(stripped);
        if (isTechnicalAction) return;

        if (hasTopLevelOperators(stripped)) {
            const children = parseRecursive(stripped, null);
            if (children.length > 0) {
                result.push({ operator, children });
            }
        } else {
            result.push({ operator, content: stripped });
        }
    });

    return result;
};

const stripOuterParentheses = (text: string): string => {
    let s = text.trim();
    while (s.startsWith('(') && s.endsWith(')')) {
        let count = 0;
        let balanced = true;
        for (let j = 0; j < s.length - 1; j++) {
            if (s[j] === '(') count++;
            if (s[j] === ')') count--;
            if (count === 0 && j > 0) {
                balanced = false;
                break;
            }
        }
        if (balanced) {
            s = s.substring(1, s.length - 1).trim();
        } else {
            break;
        }
    }
    return s;
};

const hasTopLevelOperators = (text: string): boolean => {
    let parenthesisCount = 0;
    let betweenCount = 0;
    let inQuote = false;
    let quoteChar = '';

    for (let i = 0; i < text.length; i++) {
        const char = text[i];
        if ((char === "'" || char === '"') && text[i - 1] !== '\\') {
            if (!inQuote) { inQuote = true; quoteChar = char; }
            else if (char === quoteChar) inQuote = false;
        }
        if (!inQuote) {
            if (char === '(') parenthesisCount++;
            if (char === ')') parenthesisCount--;
        }
        if (!inQuote && parenthesisCount === 0) {
            const sub = text.substring(i).toUpperCase();

            if (sub.startsWith(' BETWEEN ')) {
                betweenCount++;
                i += 8;
                continue;
            } else if (sub.startsWith('BETWEEN ')) {
                betweenCount++;
                i += 7;
                continue;
            }

            if (sub.startsWith(' AND ')) {
                if (betweenCount > 0) {
                    betweenCount--;
                    i += 4;
                    continue;
                }
                return true;
            }
            if (sub.startsWith(' OR ')) {
                return true;
            }
        }
    }
    return false;
};
