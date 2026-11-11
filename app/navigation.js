// Fragment routes and in-page focus targets share the URL hash. Keep the skip
// link out of the router so it cannot discard filters or interrupt evidence loads.
export function bindSkipLink(link, main) {
 link.addEventListener('click', event => {
  event.preventDefault();
  main.focus({preventScroll:true});
  main.scrollIntoView({block:'start'});
 });
}
