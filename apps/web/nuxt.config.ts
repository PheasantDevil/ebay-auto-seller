export default defineNuxtConfig({
  // SPA mode (no SSR).
  ssr: false,
  typescript: {
    typeCheck: true,
  },
  runtimeConfig: {
    apiBaseUrl: process.env.API_BASE_URL ?? '',
  },
  app: {
    head: {
      title: 'eBay Auto Seller',
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      ],
    },
  },
});
