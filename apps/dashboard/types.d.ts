declare module "gray-matter" {
  function matter(str: string, options?: any): any;
  export = matter;
}

declare module "*.css" {
  const content: Record<string, string>;
  export default content;
}
