(() => {
  "use strict";
  document.querySelectorAll("form[data-library-sort]").forEach((form) => {
    const list = form.parentElement.querySelector("[data-collection-library]");
    const keySelect = form.elements.namedItem("key");
    const directionSelect = form.elements.namedItem("direction");
    if (!list || !keySelect || !directionSelect) return;
    const collator = new Intl.Collator(form.dataset.locale || document.documentElement.lang || "en", {
      numeric: true,
      sensitivity: "base",
    });
    const sourceOrder = new Map([...list.children].map((item, index) => [item, index]));
    form.addEventListener("submit", (event) => event.preventDefault());
    const sort = () => {
      const key = keySelect.value;
      const direction = directionSelect.value === "desc" ? -1 : 1;
      const attribute = key === "name" ? "sortName" : key === "publication_date"
        ? "sortPublicationDate" : "sortUpdatedDate";
      const sorted = [...list.children].sort((left, right) => {
        const a = left.dataset[attribute] || "";
        const b = right.dataset[attribute] || "";
        if (key !== "name" && (!a || !b)) {
          if (!a && b) return 1;
          if (a && !b) return -1;
        }
        const comparison = collator.compare(a, b) * direction;
        return comparison || sourceOrder.get(left) - sourceOrder.get(right);
      });
      list.replaceChildren(...sorted);
    };
    keySelect.addEventListener("change", sort);
    directionSelect.addEventListener("change", sort);
    sort();
  });
})();
