const defaultDelay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

export function createRetryingOpenAlexClient({ client, delay = defaultDelay, maxAttempts = 3, baseDelayMs = 2_000 }) {
  return Object.freeze({
    async expand(options) {
      for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        try {
          return await client.expand(options);
        } catch (error) {
          if (error?.code !== "OPENALEX_PROVIDER_ERROR" || attempt === maxAttempts) throw error;
          await delay(baseDelayMs * (2 ** (attempt - 1)));
        }
      }
      throw new Error("OpenAlex retry loop ended without a result.");
    },
  });
}
