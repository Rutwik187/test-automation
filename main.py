import os
import requests
import xml.etree.ElementTree as ET

class APIAutomation:
    def __init__(self):
        self.url = "https://api.accelya.io/ha/uat/oc"
        self.subscription_key = "51e310c2f2454d97a1ec4dc789d809b0"
        self.responses_folder = "api_responses"
        
        # Get the directory containing the script
        script_dir = os.path.dirname(os.path.abspath(__file__))

        
        # Load XML templates using relative paths
        with open(os.path.join(script_dir, 'AS.txt'), 'r') as file:
            self.airshopping_template = file.read()
        with open(os.path.join(script_dir, 'OP.txt'), 'r') as file:
            self.offerprice_template = file.read()
        with open(os.path.join(script_dir, 'OC.txt'), 'r') as file:
            self.ordercreate_template = file.read()

    def format_xml(self, template, pseudocity, agtpwd, agy, origin, destination, departure_date, 
                    ResponseID=None, OfferID=None, OfferItemID=None):
        return template.format(
            pseudocity=pseudocity,
            agtpwd=agtpwd,
            agy=agy,
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            ResponseID=ResponseID or '',
            OfferID=OfferID or '',
            OfferItemID=OfferItemID or ''
        )

    def send_soap_request(self, xml_request):
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'Ocp-Apim-Subscription-Key': "51e310c2f2454d97a1ec4dc789d809b0"
        }
        response = requests.post(self.url, data=xml_request, headers=headers)
        response.raise_for_status()
        return response

    def save_response(self, filename, content):
        if not os.path.exists(self.responses_folder):
            os.makedirs(self.responses_folder)
        filepath = os.path.join(self.responses_folder, filename)
        with open(filepath, 'w') as file:
            file.write(content)

    def parse_air_shopping_response(self, xml_data):
        root = ET.fromstring(xml_data)
        price_classes = []
        for price_class in root.findall('.//PriceClass'):
            price_class_id = price_class.get('PriceClassID')
            name = price_class.find('Name').text
            code = price_class.find('Code').text
            price_classes.append((price_class_id, name, code))
            print(f"PriceClass: {code} - {name}")
        return price_classes, root

    def process_offers(self, root, selected_price_class, airshopping_response):
        offers = []
        for offer in root.findall('.//Offer'):
            flight_refs = offer.findall('.//FlightsOverview/FlightRef')
            for flight_ref in flight_refs:
                if flight_ref.get('PriceClassRef') == selected_price_class:
                    offers.append(offer)
                    break
        return offers

def main():
    # Initialize API automation
    api = APIAutomation()
    
    # Set parameters
    pseudocity = "BJBE"
    agtpwd = "Narayan1234"
    agy = "12992280"
    origin = "LAS"
    destination = "HNL"
    departure_date = "2024-12-02"
    
    # Step 1: Send AirShopping request
    airshopping_request = api.format_xml(
        api.airshopping_template, 
        pseudocity, agtpwd, agy, 
        origin, destination, departure_date
    )
    
    airshopping_response = api.send_soap_request(airshopping_request)
    api.save_response("AirShoppingResponse.xml", airshopping_response.text)
    
    # Step 2: Parse response and get price classes
    price_classes, root = api.parse_air_shopping_response(airshopping_response.text)
    
    if not price_classes:
        print("No price classes found in the response.")
        return
    
    # Step 3: Get user selection
    selected_code = input("\nEnter the PriceClass Code you want to use: ")
    
    # Step 4: Find selected price class
    selected_price_class = None
    for price_class_id, name, code in price_classes:
        if code == selected_code:
            selected_price_class = price_class_id
            break
    
    if not selected_price_class:
        print(f"No PriceClass found for code: {selected_code}")
        return
    
    # Step 5: Process offers
    offers = api.process_offers(root, selected_price_class, airshopping_response)
    
    if not offers:
        print("No offers found for the selected price class.")
        return
    
    # Step 6: Process offers and make OfferPrice call for the first offer
    if offers:
        # Get the first offer
        first_offer = offers[0]
        offer_id = first_offer.get('OfferID')
        offer_item = first_offer.find('.//OfferItem')
        
        # Get ResponseID from AirShoppingResponse
        response_id = root.find('.//ShoppingResponseID/ResponseID')
        response_id_text = response_id.text if response_id is not None else 'N/A'
        
        if offer_item is not None:
            offer_item_id = offer_item.get('OfferItemID')
            
            # Get price information and display AirShopping details
            total_price = first_offer.find('.//TotalPrice/DetailCurrencyPrice/Total')
            if total_price is not None:
                price = total_price.text
                currency = total_price.get('Code')
                print(f"\n=== AirShopping Offer Details ===")
                print(f"ResponseID: {response_id_text}")
                print(f"OfferID: {offer_id}")
                print(f"OfferItemID: {offer_item_id}")
                print(f"Total Price: {price} {currency}")
            
            # Make OfferPrice API call
            print("\nMaking OfferPrice API call...")
            offerprice_request = api.format_xml(
                api.offerprice_template,
                pseudocity=pseudocity,
                agtpwd=agtpwd,
                agy=agy,
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                ResponseID=response_id_text,
                OfferID=offer_id,
                OfferItemID=offer_item_id
            )
            
            try:
                offerprice_response = api.send_soap_request(offerprice_request)
                api.save_response("OfferPriceResponse.xml", offerprice_response.text)
                print("OfferPrice request successful! Response saved to OfferPriceResponse.xml")
                
                # Parse OfferPrice response
                op_root = ET.fromstring(offerprice_response.text)
                
                # Extract IDs from OfferPrice response
                op_response_id = op_root.find('.//ShoppingResponseID/ResponseID')
                op_offer = op_root.find('.//PricedOffer')
                op_offer_item = op_root.find('.//OfferItem')
                
                # Store the values for OrderCreate
                response_id = op_response_id.text if op_response_id is not None else None
                offer_id = op_offer.get('OfferID') if op_offer is not None else None
                offer_item_id = op_offer_item.get('OfferItemID') if op_offer_item is not None else None
                
                print(f"\n=== OfferPrice Response Details ===")
                print(f"ResponseID: {response_id}")
                print(f"OfferID: {offer_id}")
                print(f"OfferItemID: {offer_item_id}")
                
                # Proceed with OrderCreate if we have all required IDs
                if response_id and offer_id and offer_item_id:
                    print("\nMaking OrderCreate API call...")
                    
                    # Format OrderCreate request with values from OfferPrice
                    ordercreate_request = api.format_xml(
                        api.ordercreate_template,
                        pseudocity=pseudocity,
                        agtpwd=agtpwd,
                        agy=agy,
                        origin=origin,
                        destination=destination,
                        departure_date=departure_date,
                        ResponseID=response_id,
                        OfferID=offer_id,
                        OfferItemID=offer_item_id
                    )
                    
                    # Send OrderCreate request
                    ordercreate_response = api.send_soap_request(ordercreate_request)
                    api.save_response("OrderCreateResponse.xml", ordercreate_response.text)
                    print("OrderCreate request successful! Response saved to OrderCreateResponse.xml")
                    
                    # Parse OrderCreate response
                    oc_root = ET.fromstring(ordercreate_response.text)
                    
                    print("\n=== OrderCreate Response Details ===")
                    
                    # Get OrderID
                    order = oc_root.find('.//Order')
                    if order is not None:
                        order_id = order.get('OrderID')
                        print(f"OrderID: {order_id}")  # HA173HN5TS5A2
                    
                    # Get BookingReferences
                    booking_refs = oc_root.findall('.//BookingReference')
                    if booking_refs:
                        print("\nBooking References:")
                        for ref in booking_refs:
                            ref_id = ref.find('ID')
                            airline = ref.find('AirlineID')
                            other = ref.find('OtherID')
                            if ref_id is not None:
                                if airline is not None:
                                    print(f"Airline ({airline.text}) Reference: {ref_id.text}")  # HAA: 3TEHVK
                                elif other is not None:
                                    print(f"Other ({other.text}) Reference: {ref_id.text}")      # F1: BN5TS5
                    
                    # Get TicketDocNbr
                    ticket_doc = oc_root.find('.//TicketDocument/TicketDocNbr')
                    if ticket_doc is not None:
                        print(f"\nTicket Document Number: {ticket_doc.text}")  # 17357558930854
                    
                    # Get OrderItemIDs from both Payment and OrderItem sections
                    print("\nOrder Items:")
                    
                    # From Payment section
                    payment_order_item = oc_root.find('.//Payment/OrderItemID')
                    if payment_order_item is not None:
                        print(f"Payment OrderItemID: {payment_order_item.text}")
                    
                    # From OrderItems section
                    order_items = oc_root.findall('.//OrderItem')
                    if order_items:
                        for item in order_items:
                            item_id = item.get('OrderItemID')
                            print(f"OrderItem OrderItemID: {item_id}")
                    
                else:
                    print("Missing required IDs for OrderCreate request")
                    
            except Exception as e:
                print(f"Error in API processing: {e}")
    else:
        print("No offers found to process.")

if __name__ == '__main__':
    main()