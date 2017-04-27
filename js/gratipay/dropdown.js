Gratipay.Dropdown = function(selector) {
    var $ul = $(selector);
    var $labels = $('label', $ul);

    // state for vertical position
    var topFactor = 0;      // float between 0 and $labels.length-1
    var maxTopFactor = $labels.length - 1;

    // state for hovering
    var hoverIndex = 0;     // int between 0 and $labels.length-1
    var cursorOffset = 0;   // negative or positive int

    $('<div>').addClass('gratipay-dropdown-wrapper').insertAfter($ul).append($ul.remove());

    function unhover() {
        $(this).removeClass('hover');
    }

    function hover() {

        // Implement hover here instead of depending on CSS, in order to get
        // consistent behavior during scrolling. The :hover pseudoclass doesn't
        // always fire after scrolling.

        var $label = $(this);
        unhover.call($('.hover'), $ul);
        $label.addClass('hover');
        if ($ul.hasClass('open'))
            cursorOffset = $labels.index($label) - Math.round(topFactor);
    }

    function moveTo(t) {
        $ul.css({'top': -64 * t});

        var index = Math.round(t) + cursorOffset;
        if (index !== hoverIndex) {
            hoverIndex = index;
            unhover.call($('.hover'), $ul);

            // Don't call the hover function, because we don't want to
            // change cursorOffset. Just apply the class.
            $labels.eq(hoverIndex).addClass('hover');
        }
        topFactor = t;
    }

    function open($label) {
        $ul.addClass('open');
        moveTo($labels.index($label));
        lockWindowScrolling();
        $ul.mousewheel(scroll);
    }

    function close($label) {
        if ($label) {
            $('.selected', $ul).removeClass('selected')
            $label.closest('li').addClass('selected');
        }
        $ul.css({'top': 0}).removeClass('open');
        $ul.unbind('mousewheel');
        unlockWindowScrolling();
        cursorOffset = 0;
    }

    function select(e) {
        ($ul.hasClass('open') ? close : open)($(this));
    }

    function clear(e) {
        if (!$ul.hasClass('open')) return;
        if ($ul.is(e.target) || $ul.has(e.target).length > 0) return;
        close();
    }

    $('label', $ul).click(select).hover(hover, unhover);
    $('html').click(clear);


    // http://stackoverflow.com/a/3656618

    function lockWindowScrolling() {
        var scrollPosition = [
            self.pageXOffset || document.documentElement.scrollLeft || document.body.scrollLeft,
            self.pageYOffset || document.documentElement.scrollTop  || document.body.scrollTop
        ];
        var html = jQuery('html');
        html.data('scroll-position', scrollPosition);
        html.data('previous-overflow', html.css('overflow'));
        html.css('overflow', 'hidden');
        window.scrollTo(scrollPosition[0], scrollPosition[1]);
    }

    function unlockWindowScrolling() {
        var html = jQuery('html');
        var scrollPosition = html.data('scroll-position');
        html.css('overflow', html.data('previous-overflow'));
        if (scrollPosition !== undefined)
            window.scrollTo(scrollPosition[0], scrollPosition[1])
    }


    // http://stackoverflow.com/a/23961723

    var scrollThrottle = null;
    function scroll(e) {
        if (scrollThrottle !== null) return;
        window.setTimeout(function() {
            var t = topFactor, by = e.deltaY / 128; // divisor arrived at experimentally
            by = by * e.deltaFactor;
            t = t - by;
            if (t < 0) t = 0;
            if (t > maxTopFactor) t = maxTopFactor;
            moveTo(t);
            scrollThrottle = null;
        }, 12); // timeout arrived at experimentally; needs to feel instant
                // while suppressing extraneous scroll events
    }
};
