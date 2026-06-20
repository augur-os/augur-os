import fs from "fs";
import path from "path";
import { parseArgs } from "util";

// Parse command line arguments
const { values } = parseArgs({
  args: process.argv.slice(2),
  options: {
    name: { type: "string" },
    variant: { type: "string", default: "default" },
  },
});

const componentName = values.name;
if (!componentName) {
  console.error("Error: --name argument is required");
  process.exit(1);
}

const UI_DIR = path.join(process.cwd(), "components/ui");
const COMPONENT_FILE = path.join(UI_DIR, `${componentName}.tsx`);
const TEST_FILE = path.join(UI_DIR, `${componentName}.test.tsx`);
const INDEX_FILE = path.join(UI_DIR, "index.ts");

// Ensure directories exist
if (!fs.existsSync(UI_DIR)) {
  console.log(`Creating directory: ${UI_DIR}`);
  fs.mkdirSync(UI_DIR, { recursive: true });
}

// 1. Create Component File
if (fs.existsSync(COMPONENT_FILE)) {
  console.error(
    `Error: Component ${componentName} already exists at ${COMPONENT_FILE}`,
  );
  process.exit(1);
}

const componentTemplate = `import * as React from "react"
import { cn } from "@/lib/utils"

export interface ${componentName}Props extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "${values.variant}" | "outline" | "ghost";
}

const ${componentName} = React.forwardRef<HTMLDivElement, ${componentName}Props>(
  ({ className, variant = "default", ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "rounded-md p-4 transition-colors",
          variant === "default" && "bg-primary text-primary-foreground shadow",
          variant === "outline" && "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
          variant === "ghost" && "hover:bg-accent hover:text-accent-foreground",
          className
        )}
        {...props}
      />
    )
  }
)
${componentName}.displayName = "${componentName}"

export { ${componentName} }
`;

fs.writeFileSync(COMPONENT_FILE, componentTemplate);
console.log(`✅ Created component: ${COMPONENT_FILE}`);

// 2. Create Test File
const testTemplate = `import React from 'react'
import { render, screen } from '@testing-library/react'
import { ${componentName} } from './${componentName}'

describe('${componentName}', () => {
  it('renders correctly', () => {
    render(<${componentName}>Test Content</${componentName}>)
    const element = screen.getByText('Test Content')
    expect(element).toBeInTheDocument()
  })

  it('applies variant classes', () => {
    render(<${componentName} variant="outline" data-testid="${componentName.toLowerCase()}">Test</${componentName}>)
    const element = screen.getByTestId('${componentName.toLowerCase()}')
    expect(element.className).toContain('border')
  })
})
`;

fs.writeFileSync(TEST_FILE, testTemplate);
console.log(`✅ Created test: ${TEST_FILE}`);

// 3. Update Index File (Barrel Code)
// Only append if not already exported
if (fs.existsSync(INDEX_FILE)) {
  const indexContent = fs.readFileSync(INDEX_FILE, "utf-8");
  if (!indexContent.includes(`export * from "./${componentName}"`)) {
    fs.appendFileSync(INDEX_FILE, `\nexport * from "./${componentName}"`);
    console.log(`✅ Updated index: ${INDEX_FILE}`);
  }
} else {
  fs.writeFileSync(INDEX_FILE, `export * from "./${componentName}"`);
  console.log(`✅ Created index: ${INDEX_FILE}`);
}

console.log(`\nSuccess! Created ${componentName} component.`);
console.log(
  `👀 Preview at: http://localhost:3000/preview?component=${componentName}`,
);
