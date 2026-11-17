/// <reference types="vite/client" />

declare module '@demo-scenarios' {
    const scenarios: unknown;
    export default scenarios;
}

declare module '@benchmark-manifest?raw' {
    const content: string;
    export default content;
}

declare module '@benchmark-runs?raw' {
    const content: string;
    export default content;
}
