/**
 * Utility for consistent date formatting across the application
 * forcing Europe/Rome timezone.
 */

const ensureUtc = (dateStr: string): string => {
    if (!dateStr) return dateStr;
    if (dateStr.includes('T') && !dateStr.includes('Z') && !dateStr.includes('+')) {
        return `${dateStr}Z`;
    }
    return dateStr;
};

export const formatRunDate = (dateStr: string): string => {
    if (!dateStr) return 'N/D';

    const date = new Date(ensureUtc(dateStr));
    if (isNaN(date.getTime())) return 'N/D';

    const now = new Date();

    // Check if it's today
    const isToday = date.toDateString() === now.toDateString();

    // Use Intl.DateTimeFormat for robust timezone handling
    const timeFormatter = new Intl.DateTimeFormat('it-IT', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        timeZone: 'Europe/Rome'
    });

    const fullFormatter = new Intl.DateTimeFormat('it-IT', {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        timeZone: 'Europe/Rome'
    });

    const yearFormatter = new Intl.DateTimeFormat('it-IT', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        timeZone: 'Europe/Rome'
    });

    if (isToday) {
        return timeFormatter.format(date);
    }

    const isThisYear = date.getFullYear() === now.getFullYear();
    if (isThisYear) {
        return fullFormatter.format(date);
    }

    return yearFormatter.format(date);
};

/**
 * Full date formatter for details view
 */
export const formatFullDate = (dateStr: string): string => {
    if (!dateStr) return 'N/D';
    const date = new Date(ensureUtc(dateStr));
    if (isNaN(date.getTime())) return 'N/D';

    return new Intl.DateTimeFormat('it-IT', {
        day: '2-digit',
        month: 'long',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
        timeZone: 'Europe/Rome'
    }).format(date);
};
