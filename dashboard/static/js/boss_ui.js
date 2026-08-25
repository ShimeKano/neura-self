/* Boss configuration UI enhancements. */
(function () {
    const originalIsListField = window.isListField;
    window.isListField = function (path) {
        return (typeof originalIsListField === 'function' && originalIsListField(path))
            || path === 'boss.target_guilds';
    };

    if (window.CONFIG_CATEGORY_HINTS) {
        window.CONFIG_CATEGORY_HINTS.boss = 'Auto-join Boss battles in selected guilds';
    }
})();
