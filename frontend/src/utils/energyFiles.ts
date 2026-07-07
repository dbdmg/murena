export const getEnergyFileName = (path: string): string => {
    const parts = path.split(/[/\\]/);
    return parts[parts.length - 1] || path;
};

export const getEnergyCertificateLabel = (path: string): string => {
    const fileName = getEnergyFileName(path);
    const withoutExtension = fileName.replace(/\.xml$/i, '');
    return withoutExtension.split('_')[1] || withoutExtension;
};
