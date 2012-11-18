var geoCodeURL = "http://nominatim.openstreetmap.org/search";
search_options = {
       source: function ( request, response ) {
           $.ajax({
                  url: geoCodeURL,
                  dataType: "json",
                  data: {
                      format: "json",
                      viewbox: "14.3081641,50.2,14.5718359,49.9355541",
                      bounded: 1,
                      q: request.term
                  },
                  success: function ( data ) {
                      response ( $.map( data, function( item ) {
                          return {
                              label: item.display_name,
                              value: item.display_name,
                              lat: item.lat,
                              lon: item.lon
                          }}));

                      }
                  })
        },
        minLength: 2,
        delay: 200,
        select: function (e, ui) {
            lonlat = new OpenLayers.LonLat( ui.item.lon, ui.item.lat).transform(
                  new OpenLayers.Projection("EPSG:4326"),
                  map.getProjectionObject()
            );
            if (e.target.id == "jpStartStreetSearch") {
                marker = startMarker;
                $('#jpFinishStreetSearch').focus();
            } else {
                marker = endMarker;
                //$('#jpPlanButton').click();
            };
            map.setCenter(lonlat, 16);
            curpos = marker.geometry;
            marker.geometry.move(lonlat.lon - curpos.x, lonlat.lat - curpos.y);
            if (! startMarker.layer) {
                markerLayer.addFeatures(marker);
            };
            markerLayer.redraw();
            setWaypoint(marker);
        },
        open: function () {
            $( this ).removeClass( "ui-corner-all" ).addClass( "ui-corner-top");
        },
        close: function () {
            $( this ).removeClass( "ui-corner-top").addClass("ui-corner-all");
        },
        //selectFirst: true,
        autoFocus: true 
};

/*
* jQuery UI Autocomplete Select First Extension
*
* Copyright 2010, Scott González (http://scottgonzalez.com)
* Dual licensed under the MIT or GPL Version 2 licenses.
*
* http://github.com/scottgonzalez/jquery-ui-extensions
*/
/*
(function( $ ) {

$( ".ui-autocomplete-input" ).live( "autocompleteopen", function() {
var autocomplete = $( this ).data( "autocomplete" ),
menu = autocomplete.menu;

if ( !autocomplete.options.selectFirst ) {
return;
}

menu.activate( $.Event({ type: "mouseenter" }), menu.element.children().first() );
});

}( jQuery ));
*/
