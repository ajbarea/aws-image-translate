document.addEventListener("DOMContentLoaded", () => {
  const loadComponent = async (componentName, placeholderId) => {
    try {
      const response = await fetch(`components/${componentName}.html`);
      if (!response.ok) {
        throw new Error(
          `Failed to load ${componentName}.html: ${response.status} ${response.statusText}`
        );
      }
      const html = await response.text();
      const placeholder = document.getElementById(placeholderId);
      if (placeholder) {
        placeholder.innerHTML = html;
      } else {
        console.error(`Placeholder with ID '${placeholderId}' not found.`);
      }
    } catch (error) {
      console.error(`Error loading component ${componentName}:`, error);
    }
  };

  const componentsToLoad = [
    { name: "header", placeholderId: "header-placeholder" },
    { name: "login-form", placeholderId: "login-form-placeholder" },
    { name: "register-form", placeholderId: "register-form-placeholder" },
    {
      name: "confirmation-form",
      placeholderId: "confirmation-form-placeholder"
    },
    {
      name: "language-selection",
      placeholderId: "language-selection-placeholder"
    },
    { name: "file-upload", placeholderId: "file-upload-placeholder" },
    { name: "upload-list", placeholderId: "upload-list-placeholder" },
    { name: "gallery", placeholderId: "gallery-placeholder" },
    { name: "dashboard", placeholderId: "dashboard-placeholder" }
  ];

  const loadPromises = componentsToLoad.map((comp) =>
    loadComponent(comp.name, comp.placeholderId)
  );

  Promise.all(loadPromises)
    .then(() => {
      console.log("All components loaded successfully.");
      document.dispatchEvent(new CustomEvent("componentsLoaded"));
    })
    .catch((error) => {
      console.error("Failed to load one or more components:", error);
      document.dispatchEvent(
        new CustomEvent("componentsLoadFailed", { detail: error })
      );
    });
});
