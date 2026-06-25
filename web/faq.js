/* =========================================================================
   faq.js
   Drives the accordion on the homepage FAQ section. Pure progressive
   enhancement: each item is a <button> + sibling panel, toggled by
   adding/removing an "open" class. No dependency on a framework.
   ========================================================================= */

(function () {
  const items = document.querySelectorAll("#homeFaq .accordion-item");
  if (!items.length) return;

  items.forEach((item) => {
    const trigger = item.querySelector(".accordion-trigger");
    trigger.addEventListener("click", () => {
      const isOpen = item.classList.contains("open");

      // close the others (single-open accordion reads cleaner than all-open)
      items.forEach((other) => {
        if (other !== item) {
          other.classList.remove("open");
          other.querySelector(".accordion-trigger").setAttribute("aria-expanded", "false");
        }
      });

      item.classList.toggle("open", !isOpen);
      trigger.setAttribute("aria-expanded", String(!isOpen));
    });
  });
})();
