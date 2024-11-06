function changeIframeUrl(option) {
    console.log("option: " + option);

    newURL = "plots/runtime_by_time/route " + option + ".html";
    
    // Get the iframe element by its id
    var iframe = document.getElementById('speed-time-chart');

    // Change the src attribute of the iframe to the new URL
    iframe.src = newURL;
}

function changeIframeUrl_date_chart(option) {
    console.log("option: " + option);

    if (option == "System") {
        newURL = "plots/speed_by_date.html";
    }

    else {
        newURL = "plots/runtime_by_date/route " + option + ".html";
    }

    var iframe = document.getElementById('speed-date-chart');
    iframe.src = newURL;
}

//Change the colour of l1, l2, l3 etc (links) based on scroll position - whether the user is at p1, p2, p3, etc. (divs)

$(document).ready(function () {
    $(window).scroll(function () {
        pos1 = $('#p1').offset().top;
        pos2 = $('#p2').offset().top;
        pos3 = $('#p3').offset().top;
        pos4 = $('#p4').offset().top;
        pos5 = $('#p5').offset().top;
        pos6 = $('#p6').offset().top;

    //basically, add or remove the class "active" to the links based on the scroll position
    var scrollPos = $(document).scrollTop() + 300;
    if (scrollPos >= pos1 && scrollPos < pos2) {
        $('#l1').addClass('active');
        $('#l2').removeClass('active');
        $('#l3').removeClass('active');
        $('#l4').removeClass('active');
        $('#l5').removeClass('active');
        $('#l6').removeClass('active');
    } else if (scrollPos >= pos2 && scrollPos < pos3) {
        $('#l1').removeClass('active');
        $('#l2').addClass('active');
        $('#l3').removeClass('active');
        $('#l4').removeClass('active');
        $('#l5').removeClass('active');
        $('#l6').removeClass('active');
    }
    else if (scrollPos >= pos3 && scrollPos < pos4) {
        $('#l1').removeClass('active');
        $('#l2').removeClass('active');
        $('#l3').addClass('active');
        $('#l4').removeClass('active');
        $('#l5').removeClass('active');
        $('#l6').removeClass('active');
    }
    else if (scrollPos >= pos4 && scrollPos < pos5) {
        $('#l1').removeClass('active');
        $('#l2').removeClass('active');
        $('#l3').removeClass('active');
        $('#l4').addClass('active');
        $('#l5').removeClass('active');
        $('#l6').removeClass('active');
    }
    else if (scrollPos >= pos5 && scrollPos < pos6) {
        $('#l1').removeClass('active');
        $('#l2').removeClass('active');
        $('#l3').removeClass('active');
        $('#l4').removeClass('active');
        $('#l5').addClass('active');
        $('#l6').removeClass('active');
    }
    else if (scrollPos >= pos6) {
        $('#l1').removeClass('active');
        $('#l2').removeClass('active');
        $('#l3').removeClass('active');
        $('#l4').removeClass('active');
        $('#l5').removeClass('active');
        $('#l6').addClass('active');
    }
    });
});