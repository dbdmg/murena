/**
 * A centralized, premium loading component for full-page transitions.
 */
export const PageLoader = () => (
    <div className="h-full w-full flex flex-col items-center justify-center bg-[#0a0c10] animate-in fade-in duration-500">
        <div className="relative">
            <div className="w-12 h-12 border-2 border-cyan-500/20 rounded-full" />
            <div className="w-12 h-12 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin absolute inset-0" />
        </div>
        <span className="mt-4 text-cyan-500/80 text-xs font-semibold tracking-widest uppercase">Caricamento...</span>
    </div>
);
