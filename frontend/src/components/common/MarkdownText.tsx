import React from 'react';

interface MarkdownTextProps {
    text: string;
    className?: string;
}

export const MarkdownText: React.FC<MarkdownTextProps> = ({ text, className = '' }) => {
    if (!text) return null;

    // Helper to parse inline bolding: **text**
    const parseInline = (line: string): React.ReactNode[] => {
        const parts = line.split(/(\*\*.*?\*\*)/g);
        return parts.map((part, index) => {
            if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={index} className="font-bold text-white">{part.slice(2, -2)}</strong>;
            }
            return part;
        });
    };

    // Split text into paragraphs/lines
    const lines = text.split('\n');
    const elements: React.ReactNode[] = [];
    let currentList: React.ReactNode[] = [];

    const flushList = (key: number) => {
        if (currentList.length > 0) {
            elements.push(
                <ul key={`list-${key}`} className="list-disc pl-5 my-2 space-y-1 text-gray-300">
                    {currentList}
                </ul>
            );
            currentList = [];
        }
    };

    lines.forEach((line, index) => {
        const trimmed = line.trim();
        
        // Match bullet lists starting with - or *
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
            const content = trimmed.substring(2);
            currentList.push(
                <li key={`li-${index}`} className="leading-relaxed">
                    {parseInline(content)}
                </li>
            );
        } else if (trimmed === '') {
            flushList(index);
            // Add a paragraph gap or margin
            elements.push(<div key={`gap-${index}`} className="h-3" />);
        } else {
            flushList(index);
            elements.push(
                <p key={`p-${index}`} className="leading-relaxed text-gray-300">
                    {parseInline(line)}
                </p>
            );
        }
    });

    flushList(lines.length);

    return <div className={`space-y-2 ${className}`}>{elements}</div>;
};
