/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // Premium Dark Palette
                background: {
                    DEFAULT: "#0f1115", // Very dark grey/blue
                    paper: "#181b21",   // Slightly lighter for cards
                    elevated: "#22262e" // Modals/Popovers
                },
                primary: {
                    DEFAULT: "#3b82f6", // Royal Blue
                    hover: "#2563eb",
                    light: "#60a5fa"
                },
                accent: {
                    DEFAULT: "#10b981", // Emerald
                    hover: "#059669"
                },
                text: {
                    primary: "#f3f4f6", // Cool white
                    secondary: "#9ca3af", // Grey text
                    muted: "#6b7280"
                },
                border: {
                    DEFAULT: "#2d3748",
                    light: "#4b5563"
                }
            },
            fontFamily: {
                sans: ['Inter', 'sans-serif'],
            }
        },
    },
    plugins: [],
}
