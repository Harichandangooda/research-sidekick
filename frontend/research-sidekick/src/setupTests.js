// jest-dom adds custom jest matchers for asserting on DOM nodes.
// allows you to do things like:
// expect(element).toHaveTextContent(/react/i)
// learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom';

// This version of jsdom does not expose the browser Web Crypto API.
Object.defineProperty(window, 'crypto', { value: require('crypto').webcrypto, configurable: true });
