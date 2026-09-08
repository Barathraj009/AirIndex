const { createApp } = require('./src/app');
const config = require('./src/config/env');
const logger = require('./src/utils/logger');

// Standalone bootstrapping for the reusable module's demo/dev mode.
// Host applications don't use this file — they mount the module's routes
// inside their own Express app (see INTEGRATION.md) or run the API as a
// microservice via createApp().
const app = createApp({ serveDemo: true });

app.listen(config.port, () => {
  logger.info(`AirIndex India OTP auth service listening on http://localhost:${config.port}`);
  logger.info(`Demo frontend available at http://localhost:${config.port}/`);
  logger.info(
    `Email transport: ${config.email.transport} ${
      config.email.transport === 'json'
        ? '(offline — codes are not actually emailed; see .env → EMAIL_TRANSPORT)'
        : `(delivering via ${config.gmail.user || '(no sender configured)'})`
    }`
  );
});