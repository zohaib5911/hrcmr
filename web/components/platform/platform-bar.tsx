/**
 * The red bar across every platform admin page (T17.1), so the admin tools are never mistaken for a
 * tenant page. It is a plain element, not a heading: each page keeps its own h1.
 *
 * The colour is fixed, not a theme token, so the white text keeps at least 7:1 contrast in both
 * light and dark themes (WCAG AAA for normal text).
 */
export function PlatformBar() {
  return (
    <div
      data-testid="platform-bar"
      className="bg-[#b00010] px-4 py-3 text-center text-sm font-semibold tracking-wide text-white"
    >
      Platform admin
    </div>
  );
}
