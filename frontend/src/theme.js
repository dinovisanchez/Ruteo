// iOS-style look: system colors, SF typography, large radii and translucent "glass" surfaces
const iosTheme = {
  token: {
    colorPrimary: '#007AFF',
    colorInfo: '#007AFF',
    colorSuccess: '#34C759',
    colorWarning: '#FF9500',
    colorError: '#FF3B30',
    colorText: '#1C1C1E',
    colorTextSecondary: 'rgba(60, 60, 67, 0.6)',
    colorBgLayout: '#F2F2F7',
    colorBorder: 'rgba(60, 60, 67, 0.18)',
    colorBorderSecondary: 'rgba(60, 60, 67, 0.1)',
    borderRadius: 12,
    borderRadiusLG: 20,
    borderRadiusSM: 8,
    controlHeight: 36,
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", "Segoe UI", Roboto, sans-serif',
  },
  components: {
    Layout: {
      headerBg: 'transparent',
      siderBg: 'transparent',
      bodyBg: '#F2F2F7',
      headerPadding: '0 24px',
      triggerBg: 'rgba(255, 255, 255, 0.85)',
      triggerColor: '#007AFF',
    },
    Card: { headerFontSize: 16, headerFontSizeSM: 15 },
    Button: { fontWeight: 600, primaryShadow: '0 4px 14px rgba(0, 122, 255, 0.28)', defaultShadow: 'none' },
    Segmented: { trackBg: 'rgba(118, 118, 128, 0.12)', itemSelectedBg: '#FFFFFF' },
    Table: { headerBg: '#F7F7FA', headerSplitColor: 'transparent' },
    Modal: { borderRadiusLG: 22 },
    Tag: { borderRadiusSM: 6 },
  },
};

export default iosTheme;
