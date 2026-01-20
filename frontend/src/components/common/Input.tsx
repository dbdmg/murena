import React, { type InputHTMLAttributes, forwardRef } from 'react';
import clsx from 'clsx';
import { twMerge } from 'tailwind-merge';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
    label?: string;
    error?: string;
    leftIcon?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
    ({ className, label, error, leftIcon, ...props }, ref) => {
        return (
            <div className="w-full">
                {label && (
                    <label className="block text-sm font-medium text-text-secondary mb-1.5">
                        {label}
                    </label>
                )}
                <div className="relative">
                    {leftIcon && (
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-text-muted">
                            {leftIcon}
                        </div>
                    )}
                    <input
                        ref={ref}
                        className={twMerge(
                            clsx(
                                'block w-full rounded-lg border bg-background-paper text-text-primary transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50',
                                leftIcon ? 'pl-10' : 'pl-4',
                                error
                                    ? 'border-red-500 focus:border-red-500'
                                    : 'border-border focus:border-primary',
                                'placeholder:text-text-muted py-2',
                                className
                            )
                        )}
                        {...props}
                    />
                </div>
                {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
            </div>
        );
    }
);

Input.displayName = 'Input';
