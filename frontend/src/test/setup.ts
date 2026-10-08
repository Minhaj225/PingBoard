import '@testing-library/jest-dom'

export const cleanup = async () => {
  // Cleanup after each test
  await new Promise((resolve) => setTimeout(resolve, 0))
}