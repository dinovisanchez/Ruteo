const copFormatter = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });

export const formatCop = (value) => (value === null || value === undefined ? '' : copFormatter.format(value));
