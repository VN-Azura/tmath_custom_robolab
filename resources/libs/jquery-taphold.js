// jquery-taphold plugin
(function ($) {
    "use strict";
    $.fn.taphold = function (callback) {
        return this.each(function () {
            var timer, $el = $(this);
            $el.on("mousedown touchstart", function (e) {
                timer = setTimeout(function () {
                    callback.call($el, e);
                }, 500);
            });
            $el.on("mouseup mouseleave touchend touchcancel", function () {
                clearTimeout(timer);
            });
        });
    };
})(jQuery);
