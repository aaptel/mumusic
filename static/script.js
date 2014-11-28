var BAND_IDS = [];
var QUOTE = $('<div id=post-hover>MAH TEXT</div>')

function hide_comment(id)
{
    var link = $("<a href=#>[+] expand comments</a>").click(function (e) {
        e.preventDefault();
        show_comment(id);
    });

    $("div#cont-"+id+" .comment").hide()
    $("div#p"+id+" .js-comment").first().show().html(link)
}


function show_comment(id)
{
    var link = $("<a href=#>[-] hide comments</a>").click(function (e) {
        e.preventDefault();
        hide_comment(id);
    });

    $("div#cont-"+id+" .comment").show()
    $("div#p"+id+" .js-comment").first().show().html(link)
}

function show_quote (id)
{
    var post = $("div"+id).first().clone()
    post.css({'padding':'1em', 'margin':0})

    $(document).on('mousemove', function(e) {
        QUOTE.css({
            left: e.pageX + 100,
            top: e.pageY,
        });
    });

    QUOTE.html(post)
    post.show()
    QUOTE.show()
}

function hide_quote ()
{
    QUOTE.hide()
    $(document).off('mousemove')
}


$(function() {

    QUOTE.css({
        position: 'absolute',
        border: '1px solid gray',
    });

    QUOTE.hide()
    $("body").append(QUOTE)

    $("div.post.band").each(function(i) {
        BAND_IDS.push($(this).attr('id').substring(1))
    });

    for (var i = 0; i < BAND_IDS.length; i++) {
        hide_comment(BAND_IDS[i])
    }

    $("div.post a.quotelink")
        .hover(
            function(){ show_quote($(this).attr('href')) },
            hide_quote
        )
        .click(function(e) {
            e.preventDefault();

            var anchor = $(this).attr('href')
            posts = $("div"+anchor)
            bandp = posts.filter('.band').first()
            var p = null
            if (bandp) {
                p = bandp
            } else {
                p = posts.first()
                if (!p.is(':visible')) {
                    var pid = p.parent().attr('id')
                    m = pid.match(/(\d+)/)
                    if (m) {
                        show_comment(m[1])
                    }
                }
            }
            $(document).scrollTop(p.offset().top)

        });

    $("div.post.comment").each(function() {
        var post = $(this)
        var pid = post.parent().attr('id')
        var m = pid.match(/(\d+)/)
        if (m) {
            pid = m[1]
            post.find("a.quotelink").filter(function(){
                return $(this).attr('href') == "#p"+pid
            }).addClass('bandquote')
        }
    });
});
