import type { MDXComponents } from "mdx/types";

const components: MDXComponents = {
  h2: (props) => <h2 className="text-title-2 text-label mt-8 mb-3" {...props} />,
  h3: (props) => <h3 className="text-title-3 text-label mt-6 mb-2" {...props} />,
  p: (props) => <p className="text-body text-label-secondary my-4 leading-relaxed" {...props} />,
  ul: (props) => (
    <ul className="text-body text-label-secondary my-4 list-disc space-y-2 pl-6" {...props} />
  ),
  ol: (props) => (
    <ol className="text-body text-label-secondary my-4 list-decimal space-y-2 pl-6" {...props} />
  ),
  a: (props) => <a className="text-accent-text underline underline-offset-4" {...props} />,
};

export function useMDXComponents(): MDXComponents {
  return components;
}
