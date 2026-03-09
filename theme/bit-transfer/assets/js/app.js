/* ============================================================
   bit.transfer Theme — app.js
   ============================================================ */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        initGewerbeAccordion();
        initPillsToggle();
    });

    /* ----------------------------------------------------------
       TAG PILLS TOGGLE
       Show only VISIBLE pills; rest revealed on click.
       ---------------------------------------------------------- */
    function initPillsToggle() {
        var VISIBLE = 3;
        document.querySelectorAll('.post-tags-meta').forEach(function (container) {
            var pills = container.querySelectorAll('.tag-pill');
            if (pills.length <= VISIBLE) return;

            // Hide pills after VISIBLE
            for (var i = VISIBLE; i < pills.length; i++) {
                pills[i].classList.add('pill-hidden');
            }

            // Inject toggle button
            var hidden = pills.length - VISIBLE;
            var btn = document.createElement('button');
            btn.className = 'pills-toggle';
            btn.textContent = '+' + hidden + ' weitere';
            btn.addEventListener('click', function () {
                var expanded = container.classList.toggle('pills-expanded');
                btn.textContent = expanded ? 'Weniger' : '+' + hidden + ' weitere';
            });
            container.appendChild(btn);
        });
    }

    /* ----------------------------------------------------------
       GEWERBEGRUPPEN ACCORDION
       Clicking a group label toggles its Gewerke panel.
       Only one group can be open at a time.
       ---------------------------------------------------------- */
    function initGewerbeAccordion() {
        var triggers = document.querySelectorAll('.gruppe-trigger');
        if (!triggers.length) return;

        triggers.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var gruppe = btn.closest('.gewerbegruppe');
                var panel  = gruppe.querySelector('.gruppe-gewerke');
                var isOpen = !panel.hidden;

                // Close all groups
                document.querySelectorAll('.gewerbegruppe').forEach(function (g) {
                    g.classList.remove('open');
                    g.querySelector('.gruppe-trigger').setAttribute('aria-expanded', 'false');
                    g.querySelector('.gruppe-gewerke').hidden = true;
                });

                // Open clicked group (unless it was already open)
                if (!isOpen) {
                    gruppe.classList.add('open');
                    btn.setAttribute('aria-expanded', 'true');
                    panel.hidden = false;
                }
            });
        });
    }

})();
