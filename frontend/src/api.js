// Requests use the same host as the page; Vite proxies them during development.
export async function getRecommendation(group, quiet, signal) {
  const query = new URLSearchParams({ group, quiet });
  const response = await fetch(`/api/recommend?${query}`, { signal });
  if (!response.ok) throw new Error("The library server could not complete the search. Please try again.");
  return response.json();
}
