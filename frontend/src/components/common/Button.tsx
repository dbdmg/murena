import React, { type ButtonHTMLAttributes } from 'react';
import { Loader2 } from 'lucide-react';
import clsx from 'clsx';
import { twMerge } from 'tailwind-merge';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'secondary' | 'accent' | 'ghost' | 'danger';
    size?: 'sm' | 'md' | 'lg';
    isLoading?: boolean;
    leftIcon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
    children,
    className,
    variant = 'primary',
    size = 'md',
    isLoading = false,
    leftIcon,
    disabled,
    ...props
}) => {
    const baseStyles = 'inline-flex items-center justify-center font-medium transition-all duration-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-background disabled:opacity-50 disabled:cursor-not-allowed';

    const variants = {
        primary: 'bg-primary hover:bg-primary-hover text-white shadow-lg shadow-primary/20',
        secondary: 'bg-background-elevated hover:bg-border text-text-primary border border-border',
        accent: 'bg-accent hover:bg-accent-hover text-white shadow-lg shadow-accent/20',
        ghost: 'bg-transparent hover:bg-background-elevated text-text-secondary hover:text-text-primary',
        danger: 'bg-red-600 hover:bg-red-700 text-white',
    };

    const sizes = {
        sm: 'text-xs px-3 py-1.5 h-8',
        md: 'text-sm px-4 py-2 h-10',
        lg: 'text-base px-6 py-3 h-12',
    };

    return (
        <button
            className={twMerge(clsx(baseStyles, variants[variant], sizes[size], className))}
            disabled={isLoading || disabled}
            {...props}
        >
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {!isLoading && leftIcon && <span className="mr-2">{leftIcon}</span>}
            {children}
        </button>
    );
};
