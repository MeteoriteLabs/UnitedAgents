// Helper to start Next.js dev server from the correct directory
const { execSync } = require('child_process');
const path = require('path');
process.chdir(path.join(__dirname, 'frontend'));
require('./frontend/node_modules/next/dist/bin/next');
