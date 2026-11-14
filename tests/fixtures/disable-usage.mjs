// Test and release-verification processes must never inherit permission to report.
// Reporting tests may override these only after replacing the transport with mocks.
process.env.COOKIEGUARD_USAGE_METRICS = '0';
process.env.DO_NOT_TRACK = '1';
