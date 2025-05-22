function showSystemMap(mapType) {
    var newURL = "plots/" + mapType + ".html";
    var iframe = document.getElementById('system_map');
    iframe.src = newURL;

    // Remove 'active' class from all buttons
    var buttons = document.querySelectorAll('button');
    buttons.forEach(function(button) {
        button.classList.remove('active');
    });

    // Add 'active' class to the clicked button
    var activeButton = document.querySelector('button[onclick="showSystemMap(\'' + mapType + '\')"]');
    activeButton.classList.add('active');
}

function change_dropdown_IframeUrl(option, folder, chart_id) {

    newURL = "plots/" + folder + "/route " + option + ".html";
    console.log(newURL);
    // Get the iframe element by its id
    var iframe = document.getElementById(chart_id);

    // Change the src attribute of the iframe to the new URL
    iframe.src = newURL;
}

//Change the colour of l1, l2, l3 etc (links) based on scroll position - whether the user is at p1, p2, p3, etc. (divs)

//function to remove class "active" from all links, and add class "active" to the specified link
//input: int from 1 to 7
function setLinkClasses(linkNumber) {
    for (var i = 1; i <= 7; i++) {
        if (i != linkNumber) {
            $('#l' + i).removeClass('active');
        } else {
            $('#l' + i).addClass('active');
        }
    }
}

$(document).ready(function () {
    $(window).scroll(function () {
        pos1 = $('#p1').offset().top;
        pos2 = $('#p2').offset().top;
        pos3 = $('#p3').offset().top;
        pos4 = $('#p4').offset().top;
        pos5 = $('#p5').offset().top;
        pos6 = $('#p6').offset().top;
        pos7 = $('#p7').offset().top;

        //basically, add or remove the class "active" to the links based on the scroll position
        var scrollPos = $(document).scrollTop() + 300;
        if (scrollPos >= pos1 && scrollPos < pos2) {
            setLinkClasses(1);
        } else if (scrollPos >= pos2 && scrollPos < pos3) {
            setLinkClasses(2);
        }
        else if (scrollPos >= pos3 && scrollPos < pos4) {
            setLinkClasses(3);
        }
        else if (scrollPos >= pos4 && scrollPos < pos5) {
            setLinkClasses(4);
        }
        else if (scrollPos >= pos5 && scrollPos < pos6) {
            setLinkClasses(5);
        }
        else if (scrollPos >= pos6 && scrollPos < pos7) {
            setLinkClasses(6);
        }
        else if (scrollPos >= pos7) {
            setLinkClasses(7);
        }
    });
});