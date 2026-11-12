// Guides use the Markdown subset of MDX. Reject executable constructs before compilation.
export default function remarkSafeGuides() {
  return function validate(tree, file) {
    function walk(node) {
      if (node.type === "html" || node.type.startsWith("mdx")) {
        file.fail("Guide MDX must not contain HTML, JSX, imports, exports or expressions", node);
      }
      if (["image", "imageReference"].includes(node.type)) {
        file.fail("Guide images require a reviewed code component outside MDX", node);
      }
      if (node.type === "heading" && node.depth === 1) {
        file.fail("The guide page provides its title; use level 2 or lower headings", node);
      }
      if (node.type === "link" || node.type === "definition") {
        // HTTPS sources and local anchors only; no script/data URLs or remote tracking images.
        if (!/^https:\/\/[^\s]+$/i.test(node.url) && !/^#[a-z0-9-]+$/i.test(node.url)) {
          file.fail("Guide links must use HTTPS or a local anchor", node);
        }
      }
      for (const child of node.children ?? []) walk(child);
    }
    walk(tree);
  };
}
