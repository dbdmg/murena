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
                    DEFAULT: "#4fb589", // Murena Green
                    hover: "#3da177",
                    light: "#70c39f"
                },
                accent: {
                    DEFAULT: "#34d399", // Emerald 400
                    hover: "#10b981"    // Emerald 500
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
