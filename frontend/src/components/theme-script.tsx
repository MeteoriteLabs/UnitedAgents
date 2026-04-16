// Inline theme script — prevents flash of wrong theme on load.
// This is a static, self-contained script with no user input, so XSS risk is mitigated.
export function ThemeScript() {
  return (
    <script
      // Static string literal — no dynamic user content injected
      dangerouslySetInnerHTML={{
        __html: [
          "try{",
          "var t=localStorage.getItem('ua_theme');",
          "if(t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme:dark)').matches)){",
          "document.documentElement.classList.add('dark')",
          "}",
          "}catch(e){}",
        ].join(""),
      }}
    />
  );
}
